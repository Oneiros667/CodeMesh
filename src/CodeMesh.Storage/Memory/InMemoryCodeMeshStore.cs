using System.Collections.Concurrent;
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
    IStoreHealthCheck
{
    private readonly ConcurrentDictionary<string, CodeNode> _nodes = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, CodeRelationship> _relationships = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, CodeContent> _contents = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, EmbeddingRecord> _embeddings = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, ConcurrentDictionary<string, string>> _contentRunsByRepository = new(StringComparer.Ordinal);

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
}
