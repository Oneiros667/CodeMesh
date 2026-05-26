using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;
using CodeMesh.Ingestion.Embedding;
using CodeMesh.Storage;

namespace CodeMesh.Ingestion;

public sealed class IngestionOrchestrator(
    IParserClient parserClient,
    IGraphStore graphStore,
    IContentStore contentStore,
    IVectorStore vectorStore,
    IEmbeddingProvider embeddingProvider,
    IRegistryStore? registryStore = null) : IIngestionOrchestrator
{
    public async Task<IngestionResult> IngestAsync(
        IngestionRequest request,
        CancellationToken cancellationToken = default)
    {
        var startedAt = DateTimeOffset.UtcNow;
        var repositoryRoot = Path.GetFullPath(request.RepositoryRoot);
        var repository = new RepositoryRef(
            CodeMeshHash.StableId(repositoryRoot),
            repositoryRoot);
        var ingestionRunId = CodeMeshHash.StableId(repository.Id, startedAt.ToString("O"));
        var seenAt = DateTimeOffset.UtcNow;

        var parseRequest = new ParseRequest(
            repositoryRoot,
            request.SolutionPath,
            request.ProjectPath,
            request.Language,
            request.Options ?? new Dictionary<string, string>());

        var parseResult = await parserClient.ParseAsync(parseRequest, cancellationToken)
            .ConfigureAwait(false);

        var nodes = StampNodes(parseResult.Nodes, repository, ingestionRunId, seenAt);
        var relationships = StampRelationships(parseResult.Relationships, repository, ingestionRunId, seenAt);
        var currentContents = parseResult.Contents
            .GroupBy(content => content.Hash, StringComparer.Ordinal)
            .Select(group => group.First())
            .ToArray();
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
                    .GetNodeStatesAsync(repository.Id, cancellationToken)
                    .ConfigureAwait(false);
                var existingNodeById = existingNodes
                    .GroupBy(state => state.NodeId, StringComparer.Ordinal)
                    .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);

                nodesToWrite = nodes
                    .Where(node => !IsUnchangedNode(node, existingNodeById))
                    .ToArray();
                skippedNodeCount = nodes.Count - nodesToWrite.Count;

                var existingRelationships = await incrementalGraphStore
                    .GetRelationshipStatesAsync(repository.Id, cancellationToken)
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
                    .GetContentStatesAsync(repository.Id, cancellationToken)
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
            repository,
            nodesToWrite,
            relationshipsToWrite,
            contentsToWrite,
            seenAt);

        var embeddingCount = 0;
        var skippedEmbeddingCount = 0;
        int? currentEmbeddingCount = request.SkipEmbeddings ? null : 0;

        if (!request.DryRun)
        {
            await graphStore.UpsertGraphAsync(batch, cancellationToken).ConfigureAwait(false);

            foreach (var content in batch.Contents)
            {
                if (contentStore is IRefreshableContentStore refreshableContentStore)
                {
                    await refreshableContentStore
                        .UpsertContentAsync(content, repository, ingestionRunId, seenAt, cancellationToken)
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
                        .GetEmbeddingStatesAsync(repository.Id, cancellationToken)
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
                embeddings = StampEmbeddings(embeddings, repository, ingestionRunId, seenAt);

                await vectorStore.UpsertEmbeddingsAsync(embeddings, cancellationToken)
                    .ConfigureAwait(false);

                foreach (var embedding in embeddings)
                {
                    currentEmbeddingIds.Add(embedding.Id);
                }

                if (vectorStore is IIncrementalVectorStore cleanupVectorStore)
                {
                    await cleanupVectorStore
                        .RemoveEmbeddingsExceptAsync(repository.Id, currentEmbeddingIds, cancellationToken)
                        .ConfigureAwait(false);
                }

                embeddingCount = embeddings.Count;
                currentEmbeddingCount = currentEmbeddingIds.Count;
            }

            if (graphStore is IIncrementalGraphStore cleanupGraphStore)
            {
                await cleanupGraphStore
                    .RemoveGraphExceptAsync(repository.Id, currentNodeIds, currentRelationshipIds, cancellationToken)
                    .ConfigureAwait(false);
            }
            else if (graphStore is IRefreshableGraphStore refreshableGraphStore)
            {
                await refreshableGraphStore
                    .RemoveStaleGraphAsync(repository.Id, ingestionRunId, cancellationToken)
                    .ConfigureAwait(false);
            }

            if (contentStore is IIncrementalContentStore cleanupContentStore)
            {
                await cleanupContentStore
                    .RemoveContentExceptAsync(repository.Id, currentContentHashes, cancellationToken)
                    .ConfigureAwait(false);
            }
            else if (contentStore is IRefreshableContentStore refreshableContentStore)
            {
                await refreshableContentStore
                    .RemoveStaleContentAsync(repository.Id, ingestionRunId, cancellationToken)
                    .ConfigureAwait(false);
            }

            if (!request.SkipEmbeddings &&
                vectorStore is not IIncrementalVectorStore &&
                vectorStore is IRefreshableVectorStore refreshableVectorStore)
            {
                await refreshableVectorStore
                    .RemoveStaleEmbeddingsAsync(repository.Id, ingestionRunId, cancellationToken)
                    .ConfigureAwait(false);
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
            parseResult.Diagnostics,
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
                skippedEmbeddingCount));

        if (!request.DryRun && registryStore is not null)
        {
            await WriteRegistryAsync(
                    request,
                    result,
                    parseResult,
                    currentEmbeddingCount,
                    startedAt,
                    cancellationToken)
                .ConfigureAwait(false);
        }

        return result;
    }

    private async Task WriteRegistryAsync(
        IngestionRequest request,
        IngestionResult result,
        ParseResult parseResult,
        int? currentEmbeddingCount,
        DateTimeOffset firstSeenAt,
        CancellationToken cancellationToken)
    {
        if (registryStore is null)
        {
            return;
        }

        var finishedAt = result.Run.FinishedAt ?? DateTimeOffset.UtcNow;
        var diagnostics = result.Diagnostics;
        var repositoryAlias = RepositoryAlias.FromPath(result.Repository.RootPath);
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
            result.NodeCount,
            result.RelationshipCount,
            result.ContentCount,
            currentEmbeddingCount,
            new Dictionary<string, string>
            {
                ["alias"] = repositoryAlias,
                ["language"] = request.Language,
                ["parserName"] = parseResult.ParserName,
                ["embeddingProvider"] = embeddingProvider.Provider,
                ["embeddingModel"] = embeddingProvider.Model
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
                ["parsedAt"] = parseResult.ParsedAt.ToString("O")
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
