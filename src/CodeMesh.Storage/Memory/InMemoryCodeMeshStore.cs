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
    IRegistryStore,
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

    public string Name => "memory";

    public Task UpsertGraphAsync(CodeGraphBatch batch, CancellationToken cancellationToken = default)
    {
        foreach (var node in batch.Nodes)
        {
            _nodes[node.Id] = node;
        }

        foreach (var relationship in batch.Relationships)
        {
            _relationships[relationship.Id] = relationship;
        }

        foreach (var content in batch.Contents)
        {
            _contents[content.Hash] = content;
        }

        return Task.CompletedTask;
    }

    public Task<CodeNode?> GetNodeAsync(string nodeId, CancellationToken cancellationToken = default)
    {
        _nodes.TryGetValue(nodeId, out var node);
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
