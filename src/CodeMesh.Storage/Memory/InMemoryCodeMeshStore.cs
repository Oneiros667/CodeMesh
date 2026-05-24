using System.Collections.Concurrent;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Health;

namespace CodeMesh.Storage.Memory;

public sealed class InMemoryCodeMeshStore : IGraphStore, IContentStore, IVectorStore, IStoreHealthCheck
{
    private readonly ConcurrentDictionary<string, CodeNode> _nodes = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, CodeRelationship> _relationships = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, CodeContent> _contents = new(StringComparer.Ordinal);
    private readonly ConcurrentDictionary<string, EmbeddingRecord> _embeddings = new(StringComparer.Ordinal);

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
}
