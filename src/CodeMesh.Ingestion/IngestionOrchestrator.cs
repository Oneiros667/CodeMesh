using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;
using CodeMesh.Ingestion.Embedding;
using CodeMesh.Ingestion.Summary;
using CodeMesh.Storage;

namespace CodeMesh.Ingestion;

public sealed class IngestionOrchestrator(
    IParserClient parserClient,
    IGraphStore graphStore,
    IContentStore contentStore,
    IVectorStore vectorStore,
    IEmbeddingProvider embeddingProvider,
    IRegistryStore? registryStore = null,
    INodeSummaryStore? summaryStore = null,
    ICodeSummaryProvider? summaryProvider = null) : IIngestionOrchestrator
{
    public async Task<IngestionResult> IngestAsync(
        IngestionRequest request,
        CancellationToken cancellationToken = default)
    {
        request = request with
        {
            Language = string.Join(',', CompositeParserClient.ParseLanguages(request.Language))
        };
        _ = RepositoryPathPolicy.StableFingerprint(request.PathFilter);
        var startedAt = DateTimeOffset.UtcNow;
        var repositoryRoot = Path.GetFullPath(request.RepositoryRoot);
        var git = await RepositoryGitSnapshot
            .CaptureAsync(repositoryRoot, cancellationToken)
            .ConfigureAwait(false);
        var snapshotRegistry = !request.DryRun ? registryStore as ISnapshotRegistryStore : null;
        var legacyRepositoryId = CodeMeshHash.StableId(repositoryRoot);
        var legacyRepository = snapshotRegistry is null
            ? null
            : await snapshotRegistry.GetRepositoryAsync(legacyRepositoryId, cancellationToken).ConfigureAwait(false);
        RepositoryIdentity? identity = null;
        if (snapshotRegistry is not null)
        {
            identity = await RepositoryIdentityService
                .ResolveAsync(repositoryRoot, request.ProjectId, snapshotRegistry, cancellationToken)
                .ConfigureAwait(false);
            await snapshotRegistry.UpsertCheckoutAsync(
                    new CheckoutIdentityRecord(
                        identity.CheckoutId,
                        identity.ProjectId,
                        repositoryRoot,
                        identity.CreatedAt,
                        startedAt),
                    cancellationToken)
                .ConfigureAwait(false);
        }

        var projectId = identity?.ProjectId ?? request.ProjectId ?? CodeMeshHash.StableId(repositoryRoot);
        var ingestionRunId = CodeMeshHash.StableId(projectId, startedAt.ToString("O"));
        var seenAt = DateTimeOffset.UtcNow;

        var parseRequest = new ParseRequest(
            repositoryRoot,
            request.SolutionPath,
            request.ProjectPath,
            request.Language,
            request.Options ?? new Dictionary<string, string>(),
            request.PathFilter);

        var parseResult = await parserClient.ParseAsync(parseRequest, cancellationToken)
            .ConfigureAwait(false);
        var parseErrors = parseResult.Diagnostics
            .Where(diagnostic => string.Equals(
                diagnostic.Severity,
                "error",
                StringComparison.OrdinalIgnoreCase))
            .ToArray();
        if (parseErrors.Length > 0)
        {
            throw new InvalidOperationException(
                $"Parser failed before snapshot publication: {string.Join("; ", parseErrors.Select(error => $"{error.Code}: {error.Message}"))}");
        }

        var redaction = ContentRedactor.Redact(parseResult.Contents);
        var diagnostics = parseResult.Diagnostics.ToList();
        if (redaction.RedactedContentCount > 0)
        {
            diagnostics.Add(new ParserDiagnostic(
                "CMSEC001",
                $"Redacted sensitive-looking values from {redaction.RedactedContentCount} content item(s) before persistence and model-provider calls.",
                "warning"));
        }

        var unstampedNodes = ContentRedactor.RemapNodeContentHashes(parseResult.Nodes, redaction.ContentHashMap);
        var unstampedRelationships = parseResult.Relationships;
        var currentContents = redaction.Contents
            .GroupBy(content => content.Hash, StringComparer.Ordinal)
            .Select(group => group.First())
            .ToArray();
        var computedSnapshot = SnapshotIdentity.Compute(
            projectId,
            request,
            parseResult,
            unstampedNodes,
            unstampedRelationships,
            currentContents);
        var repository = new RepositoryRef(
            projectId,
            repositoryRoot,
            git.RemoteUrl,
            git.Branch,
            git.Commit,
            projectId,
            identity?.CheckoutId,
            computedSnapshot.SnapshotId);
        var storageRepository = snapshotRegistry is null
            ? repository
            : repository with { Id = computedSnapshot.SnapshotId };
        var nodes = StampNodes(
            unstampedNodes,
            storageRepository,
            ingestionRunId,
            seenAt);
        var relationships = StampRelationships(
            unstampedRelationships,
            storageRepository,
            ingestionRunId,
            seenAt);
        var currentNodeIds = nodes
            .Select(node => node.Id)
            .ToHashSet(StringComparer.Ordinal);
        var currentRelationshipIds = relationships
            .Select(relationship => relationship.Id)
            .ToHashSet(StringComparer.Ordinal);
        var currentContentHashes = currentContents
            .Select(content => content.Hash)
            .ToHashSet(StringComparer.Ordinal);

        var nodesToWrite = nodes;
        var relationshipsToWrite = relationships;
        var contentsToWrite = currentContents;
        var skippedNodeCount = 0;
        var skippedRelationshipCount = 0;
        var skippedContentCount = 0;

        if (!request.DryRun)
        {
            if (graphStore is IIncrementalGraphStore incrementalGraphStore)
            {
                var existingNodes = await incrementalGraphStore
                    .GetNodeStatesAsync(storageRepository.Id, cancellationToken)
                    .ConfigureAwait(false);
                var existingNodeById = existingNodes
                    .GroupBy(state => state.NodeId, StringComparer.Ordinal)
                    .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);

                nodesToWrite = nodes
                    .Where(node => !IsUnchangedNode(node, existingNodeById))
                    .ToArray();
                skippedNodeCount = nodes.Count - nodesToWrite.Count;

                var existingRelationships = await incrementalGraphStore
                    .GetRelationshipStatesAsync(storageRepository.Id, cancellationToken)
                    .ConfigureAwait(false);
                var existingRelationshipById = existingRelationships
                    .GroupBy(state => state.RelationshipId, StringComparer.Ordinal)
                    .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);

                relationshipsToWrite = relationships
                    .Where(relationship => !IsUnchangedRelationship(relationship, existingRelationshipById))
                    .ToArray();
                skippedRelationshipCount = relationships.Count - relationshipsToWrite.Count;
            }

            if (contentStore is IIncrementalContentStore incrementalContentStore)
            {
                var existingContents = await incrementalContentStore
                    .GetContentStatesAsync(storageRepository.Id, cancellationToken)
                    .ConfigureAwait(false);
                var existingContentHashes = existingContents
                    .Select(state => state.ContentHash)
                    .ToHashSet(StringComparer.Ordinal);

                contentsToWrite = currentContents
                    .Where(content => !existingContentHashes.Contains(content.Hash))
                    .ToArray();
                skippedContentCount = currentContents.Length - contentsToWrite.Length;
            }
        }

        var batch = new CodeGraphBatch(
            ingestionRunId,
            storageRepository,
            nodesToWrite,
            relationshipsToWrite,
            contentsToWrite,
            seenAt);

        var embeddingCount = 0;
        var skippedEmbeddingCount = 0;
        CodeSummaryGenerationResult? summaryResult = null;
        int? currentEmbeddingCount = request.SkipEmbeddings ? null : 0;

        SnapshotPublication? publication = null;
        if (snapshotRegistry is not null && identity is not null)
        {
            publication = await BuildPublicationAsync(
                    snapshotRegistry,
                    identity,
                    repository,
                    computedSnapshot,
                    git,
                    ingestionRunId,
                    startedAt,
                    seenAt,
                    nodes.Count,
                    relationships.Count,
                    currentContents.Length,
                    currentEmbeddingCount,
                    request.SnapshotRetentionGraceSeconds,
                    cancellationToken)
                .ConfigureAwait(false);
            await snapshotRegistry
                .StageGenerationAsync(publication.Generation, publication.Snapshot, cancellationToken)
                .ConfigureAwait(false);
        }

        if (!request.DryRun)
        {
            try
            {
                await graphStore.UpsertGraphAsync(batch, cancellationToken).ConfigureAwait(false);

                foreach (var content in batch.Contents)
                {
                    if (contentStore is IRefreshableContentStore refreshableContentStore)
                    {
                        await refreshableContentStore
                            .UpsertContentAsync(content, storageRepository, ingestionRunId, seenAt, cancellationToken)
                            .ConfigureAwait(false);
                    }
                    else
                    {
                        await contentStore.UpsertContentAsync(content, cancellationToken).ConfigureAwait(false);
                    }
                }

                if (!request.SkipEmbeddings)
                {
                    var contentByHash = currentContents
                        .GroupBy(content => content.Hash, StringComparer.Ordinal)
                        .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);
                    var nodesForEmbedding = nodes;
                    var currentEmbeddingIds = new HashSet<string>(StringComparer.Ordinal);

                    if (!request.ForceEmbeddings &&
                        vectorStore is IIncrementalVectorStore incrementalVectorStore)
                    {
                        var rewrittenNodeIds = nodesToWrite
                            .Select(node => node.Id)
                            .ToHashSet(StringComparer.Ordinal);
                        var existingEmbeddings = await incrementalVectorStore
                            .GetEmbeddingStatesAsync(storageRepository.Id, cancellationToken)
                            .ConfigureAwait(false);
                        var existingEmbeddingByNodeContent = existingEmbeddings
                            .Where(embedding =>
                                string.Equals(embedding.Provider, embeddingProvider.Provider, StringComparison.Ordinal) &&
                                string.Equals(embedding.Model, embeddingProvider.Model, StringComparison.Ordinal))
                            .GroupBy(EmbeddingLookupKey, StringComparer.Ordinal)
                            .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);

                        nodesForEmbedding = nodes
                            .Where(node =>
                                rewrittenNodeIds.Contains(node.Id) ||
                                !existingEmbeddingByNodeContent.ContainsKey(EmbeddingLookupKey(node.Id, node.ContentHash)))
                            .ToArray();
                        var nodesForEmbeddingKeys = nodesForEmbedding
                            .Select(node => EmbeddingLookupKey(node.Id, node.ContentHash))
                            .ToHashSet(StringComparer.Ordinal);

                        foreach (var node in nodes.Where(node => !nodesForEmbeddingKeys.Contains(EmbeddingLookupKey(node.Id, node.ContentHash))))
                        {
                            if (existingEmbeddingByNodeContent.TryGetValue(
                                EmbeddingLookupKey(node.Id, node.ContentHash),
                                out var existingEmbedding))
                            {
                                currentEmbeddingIds.Add(existingEmbedding.EmbeddingId);
                            }
                        }

                        skippedEmbeddingCount = nodes.Count - nodesForEmbedding.Count;
                    }

                    var embeddings = await embeddingProvider
                        .EmbedAsync(nodesForEmbedding, contentByHash, cancellationToken)
                        .ConfigureAwait(false);
                    embeddings = StampEmbeddings(embeddings, storageRepository, ingestionRunId, seenAt);

                    await vectorStore.UpsertEmbeddingsAsync(embeddings, cancellationToken)
                        .ConfigureAwait(false);

                    foreach (var embedding in embeddings)
                    {
                        currentEmbeddingIds.Add(embedding.Id);
                    }

                    if (vectorStore is IIncrementalVectorStore cleanupVectorStore)
                    {
                        await cleanupVectorStore
                            .RemoveEmbeddingsExceptAsync(storageRepository.Id, currentEmbeddingIds, cancellationToken)
                            .ConfigureAwait(false);
                    }

                    embeddingCount = embeddings.Count;
                    currentEmbeddingCount = currentEmbeddingIds.Count;
                }

                if (request.IncludeSummaries)
                {
                    if (summaryStore is null || summaryProvider is null)
                    {
                        throw new InvalidOperationException("Node summaries require a summary store and summary provider.");
                    }

                    var contentByHash = currentContents
                        .GroupBy(content => content.Hash, StringComparer.Ordinal)
                        .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);
                    var summaryGenerator = new CodeSummaryGenerator(
                        summaryProvider,
                        summaryStore,
                        new CodeSummaryGenerationOptions(
                            MaxInputCharacters: request.SummaryMaxInputCharacters,
                            ReasoningTokenReserve: request.SummaryReasoningTokenReserve,
                            MaxCompletionTokens: request.SummaryMaxCompletionTokens,
                            Force: request.ForceSummaries));

                    summaryResult = await summaryGenerator
                        .GenerateAsync(storageRepository, ingestionRunId, nodes, contentByHash, cancellationToken)
                        .ConfigureAwait(false);
                }

                if (graphStore is IIncrementalGraphStore cleanupGraphStore)
                {
                    await cleanupGraphStore
                        .RemoveGraphExceptAsync(storageRepository.Id, currentNodeIds, currentRelationshipIds, cancellationToken)
                        .ConfigureAwait(false);
                }
                else if (graphStore is IRefreshableGraphStore refreshableGraphStore)
                {
                    await refreshableGraphStore
                        .RemoveStaleGraphAsync(storageRepository.Id, ingestionRunId, cancellationToken)
                        .ConfigureAwait(false);
                }

                if (contentStore is IIncrementalContentStore cleanupContentStore)
                {
                    await cleanupContentStore
                        .RemoveContentExceptAsync(storageRepository.Id, currentContentHashes, cancellationToken)
                        .ConfigureAwait(false);
                }
                else if (contentStore is IRefreshableContentStore refreshableContentStore)
                {
                    await refreshableContentStore
                        .RemoveStaleContentAsync(storageRepository.Id, ingestionRunId, cancellationToken)
                        .ConfigureAwait(false);
                }

                if (!request.IncludeSummaries &&
                    summaryStore is IIncrementalNodeSummaryStore cleanupSummaryStore)
                {
                    var currentSummaryKeys = nodes
                        .Where(CodeSummaryIdentity.IsCandidate)
                        .Select(node => CodeSummaryIdentity.LookupKey(
                            node.Id,
                            node.ContentHash,
                            CodeSummaryIdentity.SummaryKind(node)))
                        .ToHashSet(StringComparer.Ordinal);
                    var existingSummaries = await cleanupSummaryStore
                        .GetSummaryStatesAsync(storageRepository.Id, cancellationToken)
                        .ConfigureAwait(false);
                    var currentSummaryIds = existingSummaries
                        .Where(summary => currentSummaryKeys.Contains(CodeSummaryIdentity.LookupKey(
                            summary.NodeId,
                            summary.ContentHash,
                            summary.SummaryKind)))
                        .Select(summary => summary.SummaryId)
                        .ToHashSet(StringComparer.Ordinal);

                    await cleanupSummaryStore
                        .RemoveSummariesExceptAsync(storageRepository.Id, currentSummaryIds, cancellationToken)
                        .ConfigureAwait(false);
                }

                if (!request.SkipEmbeddings &&
                    vectorStore is not IIncrementalVectorStore &&
                    vectorStore is IRefreshableVectorStore refreshableVectorStore)
                {
                    await refreshableVectorStore
                        .RemoveStaleEmbeddingsAsync(storageRepository.Id, ingestionRunId, cancellationToken)
                        .ConfigureAwait(false);
                }

                if (publication is not null && snapshotRegistry is not null)
                {
                    publication = publication with
                    {
                        Snapshot = publication.Snapshot with { EmbeddingCount = currentEmbeddingCount }
                    };
                    var published = await snapshotRegistry
                        .PublishSnapshotAsync(publication, cancellationToken)
                        .ConfigureAwait(false);
                    if (!published.Published)
                    {
                        throw new InvalidOperationException(published.Conflict ?? "Snapshot slot publication failed.");
                    }
                }
            }
            catch (Exception exception) when (snapshotRegistry is not null && publication is not null)
            {
                await snapshotRegistry
                    .MarkGenerationFailedAsync(publication.Generation.GenerationId, exception.Message, CancellationToken.None)
                    .ConfigureAwait(false);
                throw;
            }
        }

        var result = new IngestionResult(
            new IngestionRun(
                ingestionRunId,
                IngestionStage.Completed,
                startedAt,
                DateTimeOffset.UtcNow,
                request.DryRun ? "Dry run completed; no stores were written." : "Ingestion completed."),
            repository,
            nodes.Count,
            relationships.Count,
            currentContents.Length,
            embeddingCount,
            diagnostics,
            new IngestionStats(
                nodes.Count,
                nodesToWrite.Count,
                skippedNodeCount,
                relationships.Count,
                relationshipsToWrite.Count,
                skippedRelationshipCount,
                currentContents.Length,
                contentsToWrite.Length,
                skippedContentCount,
                embeddingCount,
                skippedEmbeddingCount,
                summaryResult?.CandidateCount ?? 0,
                summaryResult?.WrittenCount ?? 0,
                summaryResult?.SkippedCount ?? 0,
                summaryResult?.FailedCount ?? 0),
            summaryResult?.WrittenCount ?? 0);

        if (!request.DryRun && registryStore is not null)
        {
            await WriteRegistryAsync(
                    request,
                    result,
                    parseResult,
                    currentEmbeddingCount,
                    startedAt,
                    identity?.ProjectAlias,
                    cancellationToken)
                .ConfigureAwait(false);

            if (snapshotRegistry is not null &&
                legacyRepository is not null &&
                !string.Equals(legacyRepositoryId, repository.Id, StringComparison.Ordinal))
            {
                var legacyGenerationId = $"gen_legacy_{ingestionRunId}";
                await snapshotRegistry.StageGenerationAsync(
                        new IngestionGenerationRecord(
                            legacyGenerationId,
                            repository.Id,
                            repository.CheckoutId ?? string.Empty,
                            legacyRepositoryId,
                            IngestionGenerationState.Failed,
                            startedAt,
                            result.Run.FinishedAt,
                            "Migrated absolute-path repository namespace."),
                        new SnapshotIndexRecord(
                            legacyRepositoryId,
                            repository.Id,
                            "legacy-unknown",
                            "legacy-unknown",
                            "legacy-unknown",
                            "legacy",
                            SnapshotState.Collectible,
                            legacyRepository.FirstSeenAt,
                            legacyRepository.LastSeenAt,
                            DateTimeOffset.UtcNow + TimeSpan.FromSeconds(Math.Max(0, request.SnapshotRetentionGraceSeconds)),
                            legacyGenerationId,
                            legacyRepository.NodeCount,
                            legacyRepository.RelationshipCount,
                            legacyRepository.ContentCount,
                            legacyRepository.EmbeddingCount),
                        cancellationToken)
                    .ConfigureAwait(false);
                await snapshotRegistry
                    .MigrateLegacyRepositoryAsync(legacyRepositoryId, repository.Id, cancellationToken)
                    .ConfigureAwait(false);
            }
        }

        return result;
    }

    private static async Task<SnapshotPublication> BuildPublicationAsync(
        ISnapshotRegistryStore registry,
        RepositoryIdentity identity,
        RepositoryRef repository,
        ComputedSnapshotIdentity computed,
        RepositoryGitSnapshot git,
        string ingestionRunId,
        DateTimeOffset startedAt,
        DateTimeOffset observedAt,
        int nodeCount,
        int relationshipCount,
        int contentCount,
        int? embeddingCount,
        int retentionGraceSeconds,
        CancellationToken cancellationToken)
    {
        var existingSnapshot = await registry
            .GetSnapshotAsync(computed.SnapshotId, cancellationToken)
            .ConfigureAwait(false);
        var generationId = $"gen_{ingestionRunId}";
        var slots = new List<SnapshotSlotRecord>();
        var expectations = new List<SnapshotSlotExpectation>();

        async Task AddSlotAsync(SnapshotSlotKind kind, string key)
        {
            var slotId = SlotId(repository.Id, kind, key);
            var current = await registry.ResolveSlotAsync(repository.Id, kind, key, cancellationToken)
                .ConfigureAwait(false);
            expectations.Add(new SnapshotSlotExpectation(slotId, current?.SnapshotId, current?.Version));
            slots.Add(new SnapshotSlotRecord(
                slotId,
                repository.Id,
                kind,
                key,
                computed.SnapshotId,
                current?.Version ?? 0,
                observedAt));
        }

        await AddSlotAsync(SnapshotSlotKind.CheckoutCurrent, identity.CheckoutId).ConfigureAwait(false);
        if (!git.WorkingTreeDirty && !string.IsNullOrWhiteSpace(git.Branch))
        {
            await AddSlotAsync(SnapshotSlotKind.BranchHead, $"refs/heads/{git.Branch}").ConfigureAwait(false);
        }

        return new SnapshotPublication(
            new ProjectIdentityRecord(
                repository.Id,
                identity.ProjectAlias,
                repository.RemoteUrl,
                identity.CreatedAt,
                observedAt),
            new CheckoutIdentityRecord(
                identity.CheckoutId,
                repository.Id,
                repository.RootPath,
                identity.CreatedAt,
                observedAt),
            new SnapshotIndexRecord(
                computed.SnapshotId,
                repository.Id,
                computed.SourceViewHash,
                computed.ScopeFingerprint,
                computed.ParserProfileFingerprint,
                computed.GraphSchemaVersion,
                SnapshotState.Staging,
                existingSnapshot?.CreatedAt ?? observedAt,
                observedAt,
                null,
                generationId,
                nodeCount,
                relationshipCount,
                contentCount,
                embeddingCount),
            new SnapshotObservationRecord(
                $"obs_{CodeMeshHash.StableId(identity.CheckoutId, computed.SnapshotId, ingestionRunId)}",
                repository.Id,
                identity.CheckoutId,
                computed.SnapshotId,
                git.Branch,
                git.Commit,
                git.WorkingTreeDirty,
                observedAt,
                typeof(IngestionOrchestrator).Assembly.GetName().Version?.ToString() ?? "unknown",
                ingestionRunId),
            new IngestionGenerationRecord(
                generationId,
                repository.Id,
                identity.CheckoutId,
                computed.SnapshotId,
                IngestionGenerationState.Staging,
                startedAt,
                null,
                null),
            slots,
            expectations,
            TimeSpan.FromSeconds(Math.Max(0, retentionGraceSeconds)));
    }

    private static string SlotId(string projectId, SnapshotSlotKind kind, string key)
    {
        return $"slot_{CodeMeshHash.StableId(projectId, kind.ToString(), key)}";
    }

    private async Task WriteRegistryAsync(
        IngestionRequest request,
        IngestionResult result,
        ParseResult parseResult,
        int? currentEmbeddingCount,
        DateTimeOffset firstSeenAt,
        string? projectAlias,
        CancellationToken cancellationToken)
    {
        if (registryStore is null)
        {
            return;
        }

        var finishedAt = result.Run.FinishedAt ?? DateTimeOffset.UtcNow;
        var diagnostics = result.Diagnostics;
        var repositoryAlias = projectAlias ?? RepositoryAlias.FromPath(result.Repository.RootPath);
        var activeSnapshotId = result.Repository.SnapshotId;
        var activeSlotKind = "legacy-current";
        var activeSourceViewHash = string.Empty;
        SnapshotIndexRecord? activeSnapshot = null;
        if (registryStore is ISnapshotRegistryStore snapshotRegistry)
        {
            var slots = await snapshotRegistry
                .ListSlotsAsync(result.Repository.Id, cancellationToken)
                .ConfigureAwait(false);
            var branchKey = string.IsNullOrWhiteSpace(result.Repository.Branch)
                ? null
                : $"refs/heads/{result.Repository.Branch}";
            var activeSlot = branchKey is null
                ? null
                : slots.SingleOrDefault(slot =>
                    slot.Kind == SnapshotSlotKind.BranchHead &&
                    string.Equals(slot.Key, branchKey, StringComparison.Ordinal));
            activeSlot ??= slots.SingleOrDefault(slot =>
                slot.Kind == SnapshotSlotKind.CheckoutCurrent &&
                string.Equals(slot.Key, result.Repository.CheckoutId, StringComparison.Ordinal));
            activeSnapshotId = activeSlot?.SnapshotId ?? activeSnapshotId;
            activeSlotKind = activeSlot?.Kind.ToString() ?? "unknown";
            if (!string.IsNullOrWhiteSpace(activeSnapshotId))
            {
                activeSnapshot = await snapshotRegistry
                    .GetSnapshotAsync(activeSnapshotId, cancellationToken)
                    .ConfigureAwait(false);
                activeSourceViewHash = activeSnapshot?.SourceViewHash ?? string.Empty;
            }
        }
        var repository = new RepositoryIndexRecord(
            result.Repository.Id,
            result.Repository.RootPath,
            result.Repository.RemoteUrl,
            result.Repository.Branch,
            result.Repository.Commit,
            firstSeenAt,
            finishedAt,
            result.Run.RunId,
            result.Run.Stage,
            result.Run.Message,
            activeSnapshot?.NodeCount ?? result.NodeCount,
            activeSnapshot?.RelationshipCount ?? result.RelationshipCount,
            activeSnapshot?.ContentCount ?? result.ContentCount,
            activeSnapshot?.EmbeddingCount ?? currentEmbeddingCount,
            new Dictionary<string, string>
            {
                ["alias"] = repositoryAlias,
                ["language"] = request.Language,
                ["parserName"] = parseResult.ParserName,
                ["embeddingProvider"] = embeddingProvider.Provider,
                ["embeddingModel"] = embeddingProvider.Model,
                ["summaryProvider"] = request.IncludeSummaries ? summaryProvider?.Provider ?? "none" : "none",
                ["summaryModel"] = request.IncludeSummaries ? summaryProvider?.Model ?? "none" : "none",
                ["summaryCount"] = result.SummaryCount.ToString(),
                ["projectId"] = result.Repository.ProjectId ?? result.Repository.Id,
                ["checkoutId"] = result.Repository.CheckoutId ?? string.Empty,
                ["snapshotId"] = activeSnapshotId ?? string.Empty,
                ["observedSnapshotId"] = result.Repository.SnapshotId ?? string.Empty,
                ["slotKind"] = activeSlotKind,
                ["sourceViewHash"] = activeSourceViewHash,
                ["sourceIdentityFormat"] = SnapshotIdentity.IdentityFormatVersion
            },
            repositoryAlias);
        var run = new IngestionRunIndexRecord(
            result.Run.RunId,
            result.Repository.Id,
            result.Repository.RootPath,
            result.Run.Stage,
            result.Run.StartedAt,
            result.Run.FinishedAt,
            result.Run.Message,
            parseResult.Language,
            parseResult.ParserName,
            request.SolutionPath,
            request.ProjectPath,
            request.DryRun,
            request.SkipEmbeddings,
            embeddingProvider.Provider,
            embeddingProvider.Model,
            result.NodeCount,
            result.RelationshipCount,
            result.ContentCount,
            result.EmbeddingCount,
            result.Stats,
            diagnostics.Count,
            diagnostics.Count(diagnostic => string.Equals(diagnostic.Severity, "error", StringComparison.OrdinalIgnoreCase)),
            diagnostics.Count(diagnostic => string.Equals(diagnostic.Severity, "warning", StringComparison.OrdinalIgnoreCase)),
            new Dictionary<string, string>
            {
                ["parsedAt"] = parseResult.ParsedAt.ToString("O"),
                ["includeSummaries"] = request.IncludeSummaries.ToString(),
                ["forceSummaries"] = request.ForceSummaries.ToString(),
                ["summaryProvider"] = request.IncludeSummaries ? summaryProvider?.Provider ?? "none" : "none",
                ["summaryModel"] = request.IncludeSummaries ? summaryProvider?.Model ?? "none" : "none",
                ["summaryCount"] = result.SummaryCount.ToString(),
                ["projectId"] = result.Repository.ProjectId ?? result.Repository.Id,
                ["checkoutId"] = result.Repository.CheckoutId ?? string.Empty,
                ["snapshotId"] = result.Repository.SnapshotId ?? string.Empty
            });

        await registryStore.UpsertRepositoryAsync(repository, cancellationToken)
            .ConfigureAwait(false);
        await registryStore.UpsertRunAsync(run, cancellationToken)
            .ConfigureAwait(false);
    }

    private static bool IsUnchangedNode(
        CodeNode node,
        IReadOnlyDictionary<string, StoredNodeState> existingNodeById)
    {
        return existingNodeById.TryGetValue(node.Id, out var existingNode) &&
            string.Equals(existingNode.ContentHash, node.ContentHash, StringComparison.Ordinal) &&
            string.Equals(existingNode.Fingerprint, CodeMeshFingerprint.ForNode(node), StringComparison.Ordinal);
    }

    private static bool IsUnchangedRelationship(
        CodeRelationship relationship,
        IReadOnlyDictionary<string, StoredRelationshipState> existingRelationshipById)
    {
        return existingRelationshipById.TryGetValue(relationship.Id, out var existingRelationship) &&
            string.Equals(
                existingRelationship.Fingerprint,
                CodeMeshFingerprint.ForRelationship(relationship),
                StringComparison.Ordinal);
    }

    private static string EmbeddingLookupKey(StoredEmbeddingState embedding)
    {
        return EmbeddingLookupKey(embedding.NodeId, embedding.ContentHash);
    }

    private static string EmbeddingLookupKey(string nodeId, string contentHash)
    {
        return $"{nodeId}\u001f{contentHash}";
    }

    private static IReadOnlyList<CodeNode> StampNodes(
        IReadOnlyList<CodeNode> nodes,
        RepositoryRef repository,
        string ingestionRunId,
        DateTimeOffset seenAt)
    {
        return nodes
            .Select(node => node with
            {
                Metadata = RefreshMetadata(node.Metadata, repository, ingestionRunId, seenAt)
            })
            .ToArray();
    }

    private static IReadOnlyList<CodeRelationship> StampRelationships(
        IReadOnlyList<CodeRelationship> relationships,
        RepositoryRef repository,
        string ingestionRunId,
        DateTimeOffset seenAt)
    {
        return relationships
            .Select(relationship => relationship with
            {
                Metadata = RefreshMetadata(relationship.Metadata, repository, ingestionRunId, seenAt)
            })
            .ToArray();
    }

    private static IReadOnlyList<EmbeddingRecord> StampEmbeddings(
        IReadOnlyList<EmbeddingRecord> embeddings,
        RepositoryRef repository,
        string ingestionRunId,
        DateTimeOffset seenAt)
    {
        return embeddings
            .Select(embedding => embedding with
            {
                Metadata = RefreshMetadata(embedding.Metadata, repository, ingestionRunId, seenAt)
            })
            .ToArray();
    }

    private static IReadOnlyDictionary<string, string> RefreshMetadata(
        IReadOnlyDictionary<string, string> metadata,
        RepositoryRef repository,
        string ingestionRunId,
        DateTimeOffset seenAt)
    {
        var stamped = new Dictionary<string, string>(metadata, StringComparer.Ordinal)
        {
            ["repositoryId"] = repository.Id,
            ["repositoryRoot"] = repository.RootPath,
            ["projectId"] = repository.ProjectId ?? repository.Id,
            ["checkoutId"] = repository.CheckoutId ?? string.Empty,
            ["snapshotId"] = repository.SnapshotId ?? repository.Id,
            ["ingestionRunId"] = ingestionRunId,
            ["lastSeenAt"] = seenAt.ToString("O")
        };

        if (!string.IsNullOrWhiteSpace(repository.RemoteUrl))
        {
            stamped["repositoryRemoteUrl"] = repository.RemoteUrl;
        }

        if (!string.IsNullOrWhiteSpace(repository.Branch))
        {
            stamped["repositoryBranch"] = repository.Branch;
        }

        if (!string.IsNullOrWhiteSpace(repository.Commit))
        {
            stamped["repositoryCommit"] = repository.Commit;
        }

        return stamped;
    }
}
