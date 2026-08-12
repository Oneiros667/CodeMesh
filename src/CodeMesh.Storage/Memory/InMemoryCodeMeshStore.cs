using System.Collections.Concurrent;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Health;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Storage.Memory;

public sealed class InMemoryCodeMeshStore :
    IGraphStore,
    IRefreshableGraphStore,
    IIncrementalGraphStore,
    IContentStore,
    IRefreshableContentStore,
    IIncrementalContentStore,
    IVectorStore,
    IRefreshableVectorStore,
    IIncrementalVectorStore,
    INodeSummaryStore,
    IIncrementalNodeSummaryStore,
    INodeSummaryCoverageStore,
    ISnapshotRegistryStore,
    IStoreHealthCheck
{
    private readonly ConcurrentDictionary<string, CodeNode> _nodes = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, CodeRelationship> _relationships = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, CodeContent> _contents = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, EmbeddingRecord> _embeddings = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, CodeNodeSummary> _summaries = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, ConcurrentDictionary<string, string>> _contentRunsByRepository = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, RepositoryIndexRecord> _repositories = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, IngestionRunIndexRecord> _runs = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, ProjectIdentityRecord> _projects = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, CheckoutIdentityRecord> _checkouts = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, SnapshotIndexRecord> _snapshots = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, SnapshotSlotRecord> _slots = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, SnapshotObservationRecord> _observations = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, IngestionGenerationRecord> _generations = new(StringComparer.Ordinal);
    private readonly SemaphoreSlim _publicationLock = new(1, 1);

    public string Name => "memory";

    public Task UpsertGraphAsync(CodeGraphBatch batch, CancellationToken cancellationToken = default)
    {
        foreach (var node in batch.Nodes)
        {
            _nodes[StorageKey(batch.Repository.Id, node.Id)] = node;
        }

        foreach (var relationship in batch.Relationships)
        {
            _relationships[StorageKey(batch.Repository.Id, relationship.Id)] = relationship;
        }

        foreach (var content in batch.Contents)
        {
            _contents[content.Hash] = content;
        }

        return Task.CompletedTask;
    }

    public Task<CodeNode?> GetNodeAsync(string nodeId, CancellationToken cancellationToken = default)
    {
        var node = _nodes.Values
            .Where(candidate => string.Equals(candidate.Id, nodeId, StringComparison.Ordinal))
            .OrderByDescending(candidate => MetadataValue(candidate.Metadata, "lastSeenAt"), StringComparer.Ordinal)
            .FirstOrDefault();
        return Task.FromResult(node);
    }

    public Task<IReadOnlyList<CodeRelationship>> GetRelationshipsAsync(
        string nodeId,
        int depth = 1,
        CancellationToken cancellationToken = default)
    {
        var relationships = _relationships.Values
            .Where(relationship =>
                string.Equals(relationship.SourceNodeId, nodeId, StringComparison.Ordinal) ||
                string.Equals(relationship.TargetNodeId, nodeId, StringComparison.Ordinal))
            .ToArray();

        return Task.FromResult<IReadOnlyList<CodeRelationship>>(relationships);
    }

    public Task UpsertContentAsync(CodeContent content, CancellationToken cancellationToken = default)
    {
        _contents[content.Hash] = content;
        return Task.CompletedTask;
    }

    public Task UpsertContentAsync(
        CodeContent content,
        RepositoryRef repository,
        string ingestionRunId,
        DateTimeOffset seenAt,
        CancellationToken cancellationToken = default)
    {
        _contents[content.Hash] = content;

        var runs = _contentRunsByRepository.GetOrAdd(
            content.Hash,
            _ => new ConcurrentDictionary<string, string>(StringComparer.Ordinal));
        runs[repository.Id] = ingestionRunId;

        return Task.CompletedTask;
    }

    public Task<CodeContent?> GetContentAsync(string contentHash, CancellationToken cancellationToken = default)
    {
        _contents.TryGetValue(contentHash, out var content);
        return Task.FromResult(content);
    }

    public Task UpsertEmbeddingsAsync(
        IReadOnlyList<EmbeddingRecord> embeddings,
        CancellationToken cancellationToken = default)
    {
        foreach (var embedding in embeddings)
        {
            _embeddings[embedding.Id] = embedding;
        }

        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<VectorSearchMatch>> SearchAsync(
        IReadOnlyList<float> vector,
        int limit,
        IReadOnlyDictionary<string, string>? filters = null,
        CancellationToken cancellationToken = default)
    {
        if (vector.Count == 0 || limit <= 0)
        {
            return Task.FromResult<IReadOnlyList<VectorSearchMatch>>(Array.Empty<VectorSearchMatch>());
        }

        var matches = _embeddings.Values
            .Where(embedding => embedding.Vector.Count == vector.Count)
            .Where(embedding => MatchesFilters(embedding.Metadata, filters))
            .Select(embedding => new VectorSearchMatch(
                embedding.NodeId,
                embedding.ContentHash,
                CosineSimilarity(vector, embedding.Vector),
                PreviewFor(embedding.ContentHash),
                embedding.Metadata))
            .OrderByDescending(match => match.Score)
            .Take(limit)
            .ToArray();

        return Task.FromResult<IReadOnlyList<VectorSearchMatch>>(matches);
    }

    public Task UpsertSummariesAsync(
        IReadOnlyList<CodeNodeSummary> summaries,
        CancellationToken cancellationToken = default)
    {
        foreach (var summary in summaries)
        {
            _summaries[summary.Id] = summary;
        }

        return Task.CompletedTask;
    }

    public Task<ComponentHealth> CheckAsync(CancellationToken cancellationToken = default)
    {
        IReadOnlyDictionary<string, string> metadata = new Dictionary<string, string>
        {
            ["nodes"] = _nodes.Count.ToString(),
            ["relationships"] = _relationships.Count.ToString(),
            ["contents"] = _contents.Count.ToString(),
            ["embeddings"] = _embeddings.Count.ToString()
        };

        return Task.FromResult(new ComponentHealth(
            Name,
            ComponentState.Healthy,
            "In-memory store is available.",
            metadata));
    }

    public Task RemoveStaleGraphAsync(
        string repositoryId,
        string ingestionRunId,
        CancellationToken cancellationToken = default)
    {
        foreach (var (relationshipId, relationship) in _relationships)
        {
            if (IsStale(relationship.Metadata, repositoryId, ingestionRunId))
            {
                _relationships.TryRemove(relationshipId, out _);
            }
        }

        foreach (var (nodeId, node) in _nodes)
        {
            if (IsStale(node.Metadata, repositoryId, ingestionRunId))
            {
                _nodes.TryRemove(nodeId, out _);
            }
        }

        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<StoredNodeState>> GetNodeStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        var states = _nodes.Values
            .Where(node => IsRepositoryItem(node.Metadata, repositoryId))
            .Select(node => new StoredNodeState(
                node.Id,
                node.ContentHash,
                CodeMeshFingerprint.ForNode(node)))
            .ToArray();

        return Task.FromResult<IReadOnlyList<StoredNodeState>>(states);
    }

    public Task<IReadOnlyList<StoredRelationshipState>> GetRelationshipStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        var states = _relationships.Values
            .Where(relationship => IsRepositoryItem(relationship.Metadata, repositoryId))
            .Select(relationship => new StoredRelationshipState(
                relationship.Id,
                CodeMeshFingerprint.ForRelationship(relationship)))
            .ToArray();

        return Task.FromResult<IReadOnlyList<StoredRelationshipState>>(states);
    }

    public Task RemoveGraphExceptAsync(
        string repositoryId,
        IReadOnlySet<string> currentNodeIds,
        IReadOnlySet<string> currentRelationshipIds,
        CancellationToken cancellationToken = default)
    {
        foreach (var (relationshipId, relationship) in _relationships)
        {
            if (IsRepositoryItem(relationship.Metadata, repositoryId) &&
                !currentRelationshipIds.Contains(relationship.Id))
            {
                _relationships.TryRemove(relationshipId, out _);
            }
        }

        foreach (var (nodeId, node) in _nodes)
        {
            if (IsRepositoryItem(node.Metadata, repositoryId) &&
                !currentNodeIds.Contains(node.Id))
            {
                _nodes.TryRemove(nodeId, out _);
            }
        }

        return Task.CompletedTask;
    }

    public Task RemoveStaleContentAsync(
        string repositoryId,
        string ingestionRunId,
        CancellationToken cancellationToken = default)
    {
        foreach (var (hash, runs) in _contentRunsByRepository)
        {
            if (!runs.TryGetValue(repositoryId, out var contentRunId) ||
                string.Equals(contentRunId, ingestionRunId, StringComparison.Ordinal))
            {
                continue;
            }

            runs.TryRemove(repositoryId, out _);
            if (runs.IsEmpty)
            {
                _contentRunsByRepository.TryRemove(hash, out _);
                _contents.TryRemove(hash, out _);
            }
        }

        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<StoredContentState>> GetContentStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        var states = _contentRunsByRepository
            .Where(item => item.Value.ContainsKey(repositoryId))
            .Select(item => new StoredContentState(item.Key))
            .ToArray();

        return Task.FromResult<IReadOnlyList<StoredContentState>>(states);
    }

    public Task RemoveContentExceptAsync(
        string repositoryId,
        IReadOnlySet<string> currentContentHashes,
        CancellationToken cancellationToken = default)
    {
        foreach (var (hash, runs) in _contentRunsByRepository)
        {
            if (!runs.ContainsKey(repositoryId) || currentContentHashes.Contains(hash))
            {
                continue;
            }

            runs.TryRemove(repositoryId, out _);
            if (runs.IsEmpty)
            {
                _contentRunsByRepository.TryRemove(hash, out _);
                _contents.TryRemove(hash, out _);
            }
        }

        return Task.CompletedTask;
    }

    public Task RemoveStaleEmbeddingsAsync(
        string repositoryId,
        string ingestionRunId,
        CancellationToken cancellationToken = default)
    {
        foreach (var (embeddingId, embedding) in _embeddings)
        {
            if (IsStale(embedding.Metadata, repositoryId, ingestionRunId))
            {
                _embeddings.TryRemove(embeddingId, out _);
            }
        }

        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<StoredEmbeddingState>> GetEmbeddingStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        var states = _embeddings.Values
            .Where(embedding => IsRepositoryItem(embedding.Metadata, repositoryId))
            .Select(embedding => new StoredEmbeddingState(
                embedding.Id,
                embedding.NodeId,
                embedding.ContentHash,
                embedding.Provider,
                embedding.Model))
            .ToArray();

        return Task.FromResult<IReadOnlyList<StoredEmbeddingState>>(states);
    }

    public Task RemoveEmbeddingsExceptAsync(
        string repositoryId,
        IReadOnlySet<string> currentEmbeddingIds,
        CancellationToken cancellationToken = default)
    {
        foreach (var (embeddingId, embedding) in _embeddings)
        {
            if (IsRepositoryItem(embedding.Metadata, repositoryId) &&
                !currentEmbeddingIds.Contains(embedding.Id))
            {
                _embeddings.TryRemove(embeddingId, out _);
            }
        }

        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<StoredNodeSummaryState>> GetSummaryStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        var states = _summaries.Values
            .Where(summary => string.Equals(summary.RepositoryId, repositoryId, StringComparison.Ordinal))
            .Select(summary => new StoredNodeSummaryState(
                summary.Id,
                summary.NodeId,
                summary.ContentHash,
                summary.SummaryKind,
                summary.Provider,
                summary.Model,
                summary.PromptVersion,
                summary.GenerationConfigurationFingerprint,
                summary.Status))
            .ToArray();

        return Task.FromResult<IReadOnlyList<StoredNodeSummaryState>>(states);
    }

    public Task RemoveSummariesExceptAsync(
        string repositoryId,
        IReadOnlySet<string> currentSummaryIds,
        CancellationToken cancellationToken = default)
    {
        foreach (var (summaryId, summary) in _summaries)
        {
            if (string.Equals(summary.RepositoryId, repositoryId, StringComparison.Ordinal) &&
                !currentSummaryIds.Contains(summaryId))
            {
                _summaries.TryRemove(summaryId, out _);
            }
        }

        return Task.CompletedTask;
    }

    public Task<NodeSummaryCoverage> GetSummaryCoverageAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        var summaries = _summaries.Values
            .Where(summary => string.Equals(summary.RepositoryId, repositoryId, StringComparison.Ordinal))
            .ToArray();

        var coverage = new NodeSummaryCoverage(
            repositoryId,
            summaries.Length,
            summaries.Count(summary => string.Equals(summary.Status, "completed", StringComparison.Ordinal)),
            summaries.Count(summary => string.Equals(summary.Status, "failed", StringComparison.Ordinal)),
            CountBy(summaries, summary => summary.Status),
            CountBy(summaries, summary => summary.Kind.ToString()),
            CountBy(summaries, summary => $"{summary.Provider}/{summary.Model}/{summary.PromptVersion}"),
            CountProviderModels(summaries),
            summaries
                .Where(summary => string.Equals(summary.Status, "failed", StringComparison.Ordinal))
                .OrderByDescending(summary => summary.GeneratedAt)
                .Take(10)
                .Select(summary => new NodeSummaryFailure(
                    summary.Id,
                    summary.NodeId,
                    summary.Kind.ToString(),
                    summary.Name,
                    summary.Provider,
                    summary.Model,
                    summary.PromptVersion,
                    summary.Error ?? string.Empty,
                    summary.GeneratedAt))
                .ToArray());

        return Task.FromResult(coverage);
    }

    public Task UpsertRepositoryAsync(
        RepositoryIndexRecord repository,
        CancellationToken cancellationToken = default)
    {
        var storedRepository = repository.Alias is not null || !repository.Metadata.TryGetValue("alias", out var metadataAlias)
            ? repository
            : repository with { Alias = metadataAlias };
        _repositories.AddOrUpdate(
            storedRepository.RepositoryId,
            storedRepository,
            (_, existing) => storedRepository with
            {
                FirstSeenAt = existing.FirstSeenAt,
                EmbeddingCount = storedRepository.EmbeddingCount ?? existing.EmbeddingCount
            });

        return Task.CompletedTask;
    }

    public Task UpsertRunAsync(
        IngestionRunIndexRecord run,
        CancellationToken cancellationToken = default)
    {
        _runs[run.RunId] = run;
        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<RepositoryIndexRecord>> ListRepositoriesAsync(
        int limit = 50,
        CancellationToken cancellationToken = default)
    {
        var clampedLimit = Math.Clamp(limit, 1, 500);
        var repositories = _repositories.Values
            .OrderByDescending(repository => repository.LastSeenAt)
            .Take(clampedLimit)
            .ToArray();

        return Task.FromResult<IReadOnlyList<RepositoryIndexRecord>>(repositories);
    }

    public Task<RepositoryIndexRecord?> GetRepositoryAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        if (_repositories.TryGetValue(repositoryId, out var repository))
        {
            return Task.FromResult<RepositoryIndexRecord?>(repository);
        }

        var normalizedAlias = RepositoryAlias.Normalize(repositoryId);
        var matches = _repositories.Values
            .Where(repository => MatchesRepositoryAlias(repository, repositoryId, normalizedAlias))
            .Take(2)
            .ToArray();
        if (matches.Length > 1)
        {
            throw new InvalidOperationException($"Repository alias '{repositoryId}' matches multiple repositories.");
        }

        return Task.FromResult(matches.FirstOrDefault());
    }

    public Task<IReadOnlyList<IngestionRunIndexRecord>> ListRunsAsync(
        string? repositoryId = null,
        int limit = 50,
        CancellationToken cancellationToken = default)
    {
        var clampedLimit = Math.Clamp(limit, 1, 500);
        var runs = _runs.Values
            .Where(run => string.IsNullOrWhiteSpace(repositoryId) ||
                string.Equals(run.RepositoryId, repositoryId, StringComparison.Ordinal))
            .OrderByDescending(run => run.StartedAt)
            .Take(clampedLimit)
            .ToArray();

        return Task.FromResult<IReadOnlyList<IngestionRunIndexRecord>>(runs);
    }

    public Task DeleteRepositoryAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        _repositories.TryRemove(repositoryId, out _);

        foreach (var (runId, run) in _runs)
        {
            if (string.Equals(run.RepositoryId, repositoryId, StringComparison.Ordinal))
            {
                _runs.TryRemove(runId, out _);
            }
        }

        _projects.TryRemove(repositoryId, out _);
        foreach (var (checkoutId, checkout) in _checkouts)
        {
            if (string.Equals(checkout.ProjectId, repositoryId, StringComparison.Ordinal))
            {
                _checkouts.TryRemove(checkoutId, out _);
            }
        }
        foreach (var (slotId, slot) in _slots)
        {
            if (string.Equals(slot.ProjectId, repositoryId, StringComparison.Ordinal))
            {
                _slots.TryRemove(slotId, out _);
            }
        }
        foreach (var (snapshotId, snapshot) in _snapshots)
        {
            if (string.Equals(snapshot.ProjectId, repositoryId, StringComparison.Ordinal))
            {
                _snapshots.TryRemove(snapshotId, out _);
            }
        }

        return Task.CompletedTask;
    }

    public Task<CheckoutIdentityRecord?> GetCheckoutAsync(
        string checkoutId,
        CancellationToken cancellationToken = default)
    {
        _checkouts.TryGetValue(checkoutId, out var checkout);
        return Task.FromResult(checkout);
    }

    public Task UpsertCheckoutAsync(
        CheckoutIdentityRecord checkout,
        CancellationToken cancellationToken = default)
    {
        _checkouts[checkout.CheckoutId] = checkout;
        return Task.CompletedTask;
    }

    public Task<SnapshotIndexRecord?> GetSnapshotAsync(
        string snapshotId,
        CancellationToken cancellationToken = default)
    {
        _snapshots.TryGetValue(snapshotId, out var snapshot);
        return Task.FromResult(snapshot);
    }

    public Task<IReadOnlyList<SnapshotIndexRecord>> ListSnapshotsAsync(
        string projectId,
        CancellationToken cancellationToken = default)
    {
        IReadOnlyList<SnapshotIndexRecord> snapshots = _snapshots.Values
            .Where(snapshot => string.Equals(snapshot.ProjectId, projectId, StringComparison.Ordinal))
            .OrderByDescending(snapshot => snapshot.LastReferencedAt)
            .ToArray();
        return Task.FromResult(snapshots);
    }

    public Task<IReadOnlyList<SnapshotSlotRecord>> ListSlotsAsync(
        string projectId,
        CancellationToken cancellationToken = default)
    {
        IReadOnlyList<SnapshotSlotRecord> slots = _slots.Values
            .Where(slot => string.Equals(slot.ProjectId, projectId, StringComparison.Ordinal))
            .OrderBy(slot => slot.SlotId, StringComparer.Ordinal)
            .ToArray();
        return Task.FromResult(slots);
    }

    public Task StageGenerationAsync(
        IngestionGenerationRecord generation,
        SnapshotIndexRecord snapshot,
        CancellationToken cancellationToken = default)
    {
        _generations[generation.GenerationId] = generation;
        _snapshots.AddOrUpdate(
            snapshot.SnapshotId,
            snapshot,
            (_, existing) => existing.State == SnapshotState.Active ? existing : snapshot);
        return Task.CompletedTask;
    }

    public async Task<SnapshotPublicationResult> PublishSnapshotAsync(
        SnapshotPublication publication,
        CancellationToken cancellationToken = default)
    {
        await _publicationLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            foreach (var expected in publication.ExpectedSlots)
            {
                _slots.TryGetValue(expected.SlotId, out var current);
                if (!string.Equals(current?.SnapshotId, expected.SnapshotId, StringComparison.Ordinal) ||
                    current?.Version != expected.Version)
                {
                    return new SnapshotPublicationResult(
                        false,
                        Array.Empty<SnapshotSlotRecord>(),
                        Array.Empty<string>(),
                        $"Slot '{expected.SlotId}' changed during ingestion.");
                }
            }

            var now = publication.Observation.ObservedAt;
            _projects[publication.Project.ProjectId] = publication.Project;
            _checkouts[publication.Checkout.CheckoutId] = publication.Checkout;
            _observations[publication.Observation.ObservationId] = publication.Observation;
            _generations[publication.Generation.GenerationId] = publication.Generation with
            {
                State = IngestionGenerationState.Published,
                FinishedAt = now,
                Error = null
            };
            _snapshots[publication.Snapshot.SnapshotId] = publication.Snapshot with
            {
                State = SnapshotState.Active,
                LastReferencedAt = now,
                CollectibleAfter = null
            };

            var publishedSlots = new List<SnapshotSlotRecord>();
            foreach (var requested in publication.Slots)
            {
                _slots.TryGetValue(requested.SlotId, out var current);
                var published = requested with
                {
                    Version = (current?.Version ?? 0) + 1,
                    UpdatedAt = now
                };
                _slots[published.SlotId] = published;
                publishedSlots.Add(published);
            }

            var referenced = _slots.Values
                .Where(slot => string.Equals(slot.ProjectId, publication.Project.ProjectId, StringComparison.Ordinal))
                .Select(slot => slot.SnapshotId)
                .ToHashSet(StringComparer.Ordinal);
            var newlyCollectible = new List<string>();
            foreach (var (snapshotId, snapshot) in _snapshots)
            {
                if (!string.Equals(snapshot.ProjectId, publication.Project.ProjectId, StringComparison.Ordinal) ||
                    referenced.Contains(snapshotId) ||
                    snapshot.State is SnapshotState.Failed or SnapshotState.Staging)
                {
                    continue;
                }

                var collectible = snapshot with
                {
                    State = SnapshotState.Collectible,
                    CollectibleAfter = now + publication.UnreferencedGracePeriod
                };
                _snapshots[snapshotId] = collectible;
                newlyCollectible.Add(snapshotId);
            }

            return new SnapshotPublicationResult(true, publishedSlots, newlyCollectible, null);
        }
        finally
        {
            _publicationLock.Release();
        }
    }

    public Task MarkGenerationFailedAsync(
        string generationId,
        string error,
        CancellationToken cancellationToken = default)
    {
        if (_generations.TryGetValue(generationId, out var generation))
        {
            _generations[generationId] = generation with
            {
                State = IngestionGenerationState.Failed,
                FinishedAt = DateTimeOffset.UtcNow,
                Error = error
            };
            if (_snapshots.TryGetValue(generation.SnapshotId, out var snapshot) &&
                snapshot.State == SnapshotState.Staging)
            {
                _snapshots[generation.SnapshotId] = snapshot with
                {
                    State = SnapshotState.Failed,
                    CollectibleAfter = DateTimeOffset.UtcNow
                };
            }
        }

        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<SnapshotIndexRecord>> ListCollectibleSnapshotsAsync(
        DateTimeOffset now,
        CancellationToken cancellationToken = default)
    {
        IReadOnlyList<SnapshotIndexRecord> snapshots = _snapshots.Values
            .Where(snapshot => snapshot.State is SnapshotState.Collectible or SnapshotState.Failed)
            .Where(snapshot => snapshot.CollectibleAfter is null || snapshot.CollectibleAfter <= now)
            .Where(snapshot => !_slots.Values.Any(slot => string.Equals(slot.SnapshotId, snapshot.SnapshotId, StringComparison.Ordinal)))
            .ToArray();
        return Task.FromResult(snapshots);
    }

    public Task DeleteSnapshotRecordAsync(
        string snapshotId,
        CancellationToken cancellationToken = default)
    {
        if (_slots.Values.Any(slot => string.Equals(slot.SnapshotId, snapshotId, StringComparison.Ordinal)))
        {
            throw new InvalidOperationException($"Snapshot '{snapshotId}' is still referenced by an active slot.");
        }

        _snapshots.TryRemove(snapshotId, out _);
        return Task.CompletedTask;
    }

    public Task<SnapshotSlotRecord?> ResolveSlotAsync(
        string projectId,
        SnapshotSlotKind kind,
        string key,
        CancellationToken cancellationToken = default)
    {
        var slot = _slots.Values.SingleOrDefault(candidate =>
            string.Equals(candidate.ProjectId, projectId, StringComparison.Ordinal) &&
            candidate.Kind == kind &&
            string.Equals(candidate.Key, key, StringComparison.Ordinal));
        return Task.FromResult(slot);
    }

    public Task MigrateLegacyRepositoryAsync(
        string legacyRepositoryId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        if (string.Equals(legacyRepositoryId, projectId, StringComparison.Ordinal))
        {
            return Task.CompletedTask;
        }

        _repositories.TryRemove(legacyRepositoryId, out _);
        foreach (var (runId, run) in _runs)
        {
            if (string.Equals(run.RepositoryId, legacyRepositoryId, StringComparison.Ordinal))
            {
                _runs[runId] = run with { RepositoryId = projectId };
            }
        }

        return Task.CompletedTask;
    }

    public async Task<SnapshotSlotMutationResult> UpsertRetainedSlotAsync(
        string projectId,
        SnapshotSlotKind kind,
        string key,
        string snapshotId,
        long? expectedVersion,
        CancellationToken cancellationToken = default)
    {
        await _publicationLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (!_snapshots.TryGetValue(snapshotId, out var snapshot) ||
                !string.Equals(snapshot.ProjectId, projectId, StringComparison.Ordinal))
            {
                return new SnapshotSlotMutationResult(false, null, Array.Empty<string>(), "Snapshot was not found in the project.");
            }

            var slotId = RetainedSlotId(projectId, kind, key);
            _slots.TryGetValue(slotId, out var current);
            if (expectedVersion.HasValue && current?.Version != expectedVersion)
            {
                return new SnapshotSlotMutationResult(false, current, Array.Empty<string>(), $"Slot '{slotId}' changed.");
            }

            var now = DateTimeOffset.UtcNow;
            var slot = new SnapshotSlotRecord(slotId, projectId, kind, key, snapshotId, (current?.Version ?? 0) + 1, now);
            _slots[slotId] = slot;
            _snapshots[snapshotId] = snapshot with { State = SnapshotState.Active, LastReferencedAt = now, CollectibleAfter = null };
            return new SnapshotSlotMutationResult(true, slot, Array.Empty<string>(), null);
        }
        finally
        {
            _publicationLock.Release();
        }
    }

    public async Task<SnapshotSlotMutationResult> DeleteSlotAsync(
        string projectId,
        SnapshotSlotKind kind,
        string key,
        long? expectedVersion,
        TimeSpan unreferencedGracePeriod,
        CancellationToken cancellationToken = default)
    {
        await _publicationLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            var slotId = RetainedSlotId(projectId, kind, key);
            if (!_slots.TryGetValue(slotId, out var current))
            {
                return new SnapshotSlotMutationResult(false, null, Array.Empty<string>(), null);
            }
            if (expectedVersion.HasValue && current.Version != expectedVersion)
            {
                return new SnapshotSlotMutationResult(false, current, Array.Empty<string>(), $"Slot '{slotId}' changed.");
            }

            _slots.TryRemove(slotId, out _);
            var newlyCollectible = Array.Empty<string>();
            if (!_slots.Values.Any(slot => string.Equals(slot.SnapshotId, current.SnapshotId, StringComparison.Ordinal)) &&
                _snapshots.TryGetValue(current.SnapshotId, out var snapshot))
            {
                _snapshots[current.SnapshotId] = snapshot with
                {
                    State = SnapshotState.Collectible,
                    CollectibleAfter = DateTimeOffset.UtcNow + unreferencedGracePeriod
                };
                newlyCollectible = [current.SnapshotId];
            }

            return new SnapshotSlotMutationResult(true, current, newlyCollectible, null);
        }
        finally
        {
            _publicationLock.Release();
        }
    }

    private string? PreviewFor(string contentHash)
    {
        if (!_contents.TryGetValue(contentHash, out var content))
        {
            return null;
        }

        var compact = content.Text.ReplaceLineEndings(" ").Trim();
        return compact.Length <= 180 ? compact : compact[..180];
    }

    private static double CosineSimilarity(IReadOnlyList<float> left, IReadOnlyList<float> right)
    {
        var dot = 0.0;
        var leftNorm = 0.0;
        var rightNorm = 0.0;

        for (var i = 0; i < left.Count; i++)
        {
            dot += left[i] * right[i];
            leftNorm += left[i] * left[i];
            rightNorm += right[i] * right[i];
        }

        if (leftNorm == 0 || rightNorm == 0)
        {
            return 0;
        }

        return dot / (Math.Sqrt(leftNorm) * Math.Sqrt(rightNorm));
    }

    private static bool IsStale(
        IReadOnlyDictionary<string, string> metadata,
        string repositoryId,
        string ingestionRunId)
    {
        return metadata.TryGetValue("repositoryId", out var itemRepositoryId) &&
            metadata.TryGetValue("ingestionRunId", out var itemRunId) &&
            string.Equals(itemRepositoryId, repositoryId, StringComparison.Ordinal) &&
            !string.Equals(itemRunId, ingestionRunId, StringComparison.Ordinal);
    }

    private static string StorageKey(string repositoryId, string id) => $"{repositoryId}\u001f{id}";

    private static string RetainedSlotId(string projectId, SnapshotSlotKind kind, string key)
    {
        return $"slot_{CodeMeshHash.StableId(projectId, kind.ToString(), key)}";
    }

    private static string MetadataValue(IReadOnlyDictionary<string, string> metadata, string key)
    {
        return metadata.TryGetValue(key, out var value) ? value : string.Empty;
    }

    private static bool IsRepositoryItem(
        IReadOnlyDictionary<string, string> metadata,
        string repositoryId)
    {
        return metadata.TryGetValue("repositoryId", out var itemRepositoryId) &&
            string.Equals(itemRepositoryId, repositoryId, StringComparison.Ordinal);
    }

    private static IReadOnlyDictionary<string, int> CountBy<T>(
        IEnumerable<T> items,
        Func<T, string> keySelector)
    {
        return items
            .GroupBy(item =>
            {
                var key = keySelector(item);
                return string.IsNullOrWhiteSpace(key) ? "unknown" : key;
            }, StringComparer.Ordinal)
            .OrderByDescending(group => group.Count())
            .ThenBy(group => group.Key, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Count(), StringComparer.Ordinal);
    }

    private static IReadOnlyList<NodeSummaryProviderModelCount> CountProviderModels(IEnumerable<CodeNodeSummary> summaries)
    {
        return summaries
            .GroupBy(summary => new
            {
                Provider = string.IsNullOrWhiteSpace(summary.Provider) ? "unknown" : summary.Provider,
                Model = string.IsNullOrWhiteSpace(summary.Model) ? "unknown" : summary.Model,
                PromptVersion = string.IsNullOrWhiteSpace(summary.PromptVersion) ? "unknown" : summary.PromptVersion
            })
            .OrderByDescending(group => group.Count())
            .ThenBy(group => group.Key.Provider, StringComparer.Ordinal)
            .ThenBy(group => group.Key.Model, StringComparer.Ordinal)
            .ThenBy(group => group.Key.PromptVersion, StringComparer.Ordinal)
            .Select(group => new NodeSummaryProviderModelCount(
                group.Key.Provider,
                group.Key.Model,
                group.Key.PromptVersion,
                group.Count()))
            .ToArray();
    }

    private static bool MatchesFilters(
        IReadOnlyDictionary<string, string> metadata,
        IReadOnlyDictionary<string, string>? filters)
    {
        if (filters is null || filters.Count == 0)
        {
            return true;
        }

        foreach (var (key, value) in filters)
        {
            if (!metadata.TryGetValue(key, out var actual) ||
                !string.Equals(actual, value, StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }

    private static bool MatchesRepositoryAlias(
        RepositoryIndexRecord repository,
        string alias,
        string normalizedAlias)
    {
        return string.Equals(repository.Alias, alias, StringComparison.Ordinal) ||
            string.Equals(repository.Alias, normalizedAlias, StringComparison.Ordinal) ||
            (repository.Metadata.TryGetValue("alias", out var metadataAlias) &&
                (string.Equals(metadataAlias, alias, StringComparison.Ordinal) ||
                    string.Equals(metadataAlias, normalizedAlias, StringComparison.Ordinal)));
    }
}
