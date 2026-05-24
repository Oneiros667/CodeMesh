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

public interface IRefreshableContentStore : IContentStore
{
    Task UpsertContentAsync(
        CodeContent content,
        RepositoryRef repository,
        string ingestionRunId,
        DateTimeOffset seenAt,
        CancellationToken cancellationToken = default);

    Task RemoveStaleContentAsync(
        string repositoryId,
        string ingestionRunId,
        CancellationToken cancellationToken = default);
}

public sealed record StoredContentState(string ContentHash);

public interface IIncrementalContentStore : IContentStore
{
    Task<IReadOnlyList<StoredContentState>> GetContentStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default);

    Task RemoveContentExceptAsync(
        string repositoryId,
        IReadOnlySet<string> currentContentHashes,
        CancellationToken cancellationToken = default);
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

public interface IRefreshableGraphStore : IGraphStore
{
    Task RemoveStaleGraphAsync(
        string repositoryId,
        string ingestionRunId,
        CancellationToken cancellationToken = default);
}

public sealed record StoredNodeState(
    string NodeId,
    string ContentHash,
    string Fingerprint);

public sealed record StoredRelationshipState(
    string RelationshipId,
    string Fingerprint);

public interface IIncrementalGraphStore : IGraphStore
{
    Task<IReadOnlyList<StoredNodeState>> GetNodeStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<StoredRelationshipState>> GetRelationshipStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default);

    Task RemoveGraphExceptAsync(
        string repositoryId,
        IReadOnlySet<string> currentNodeIds,
        IReadOnlySet<string> currentRelationshipIds,
        CancellationToken cancellationToken = default);
}

public interface IRefreshableVectorStore : IVectorStore
{
    Task RemoveStaleEmbeddingsAsync(
        string repositoryId,
        string ingestionRunId,
        CancellationToken cancellationToken = default);
}

public sealed record StoredEmbeddingState(
    string EmbeddingId,
    string NodeId,
    string ContentHash,
    string Provider,
    string Model);

public interface IIncrementalVectorStore : IVectorStore
{
    Task<IReadOnlyList<StoredEmbeddingState>> GetEmbeddingStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default);

    Task RemoveEmbeddingsExceptAsync(
        string repositoryId,
        IReadOnlySet<string> currentEmbeddingIds,
        CancellationToken cancellationToken = default);
}

public interface IStoreHealthCheck
{
    string Name { get; }

    Task<ComponentHealth> CheckAsync(CancellationToken cancellationToken = default);
}
