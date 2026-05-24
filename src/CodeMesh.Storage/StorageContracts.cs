using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Health;

namespace CodeMesh.Storage;

public interface IGraphStore
{
    Task UpsertGraphAsync(CodeGraphBatch batch, CancellationToken cancellationToken = default);

    Task<CodeNode?> GetNodeAsync(string nodeId, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<CodeRelationship>> GetRelationshipsAsync(
        string nodeId,
        int depth = 1,
        CancellationToken cancellationToken = default);
}

public interface IContentStore
{
    Task UpsertContentAsync(CodeContent content, CancellationToken cancellationToken = default);

    Task<CodeContent?> GetContentAsync(string contentHash, CancellationToken cancellationToken = default);
}

public interface IVectorStore
{
    Task UpsertEmbeddingsAsync(
        IReadOnlyList<EmbeddingRecord> embeddings,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<VectorSearchMatch>> SearchAsync(
        IReadOnlyList<float> vector,
        int limit,
        IReadOnlyDictionary<string, string>? filters = null,
        CancellationToken cancellationToken = default);
}

public interface IStoreHealthCheck
{
    string Name { get; }

    Task<ComponentHealth> CheckAsync(CancellationToken cancellationToken = default);
}
