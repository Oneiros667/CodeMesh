using CodeMesh.Domain.Contracts;
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

public interface INodeSummaryStore
{
    Task UpsertSummariesAsync(
        IReadOnlyList<CodeNodeSummary> summaries,
        CancellationToken cancellationToken = default);
}

public sealed record StoredNodeSummaryState(
    string SummaryId,
    string NodeId,
    string ContentHash,
    string SummaryKind,
    string Provider,
    string Model,
    string PromptVersion,
    string GenerationConfigurationFingerprint,
    string Status);

public interface IIncrementalNodeSummaryStore : INodeSummaryStore
{
    Task<IReadOnlyList<StoredNodeSummaryState>> GetSummaryStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default);

    Task RemoveSummariesExceptAsync(
        string repositoryId,
        IReadOnlySet<string> currentSummaryIds,
        CancellationToken cancellationToken = default);
}

public sealed record NodeSummaryFailure(
    string SummaryId,
    string NodeId,
    string Kind,
    string Name,
    string Provider,
    string Model,
    string PromptVersion,
    string Error,
    DateTimeOffset GeneratedAt);

public sealed record NodeSummaryProviderModelCount(
    string Provider,
    string Model,
    string PromptVersion,
    int Count);

public sealed record NodeSummaryCoverage(
    string RepositoryId,
    int TotalCount,
    int CompletedCount,
    int FailedCount,
    IReadOnlyDictionary<string, int> StatusCounts,
    IReadOnlyDictionary<string, int> KindCounts,
    IReadOnlyDictionary<string, int> ProviderModelCounts,
    IReadOnlyList<NodeSummaryProviderModelCount> ProviderModelCountDetails,
    IReadOnlyList<NodeSummaryFailure> RecentFailures);

public interface INodeSummaryCoverageStore
{
    Task<NodeSummaryCoverage> GetSummaryCoverageAsync(
        string repositoryId,
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

public interface IRegistryStore
{
    Task UpsertRepositoryAsync(
        RepositoryIndexRecord repository,
        CancellationToken cancellationToken = default);

    Task UpsertRunAsync(
        IngestionRunIndexRecord run,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<RepositoryIndexRecord>> ListRepositoriesAsync(
        int limit = 50,
        CancellationToken cancellationToken = default);

    Task<RepositoryIndexRecord?> GetRepositoryAsync(
        string repositoryId,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<IngestionRunIndexRecord>> ListRunsAsync(
        string? repositoryId = null,
        int limit = 50,
        CancellationToken cancellationToken = default);

    Task DeleteRepositoryAsync(
        string repositoryId,
        CancellationToken cancellationToken = default);
}

public interface ISnapshotRegistryStore : IRegistryStore
{
    Task<CheckoutIdentityRecord?> GetCheckoutAsync(
        string checkoutId,
        CancellationToken cancellationToken = default);

    Task UpsertCheckoutAsync(
        CheckoutIdentityRecord checkout,
        CancellationToken cancellationToken = default);

    Task<SnapshotIndexRecord?> GetSnapshotAsync(
        string snapshotId,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<SnapshotIndexRecord>> ListSnapshotsAsync(
        string projectId,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<SnapshotSlotRecord>> ListSlotsAsync(
        string projectId,
        CancellationToken cancellationToken = default);

    Task StageGenerationAsync(
        IngestionGenerationRecord generation,
        SnapshotIndexRecord snapshot,
        CancellationToken cancellationToken = default);

    Task<SnapshotPublicationResult> PublishSnapshotAsync(
        SnapshotPublication publication,
        CancellationToken cancellationToken = default);

    Task MarkGenerationFailedAsync(
        string generationId,
        string error,
        CancellationToken cancellationToken = default);

    Task<IReadOnlyList<SnapshotIndexRecord>> ListCollectibleSnapshotsAsync(
        DateTimeOffset now,
        CancellationToken cancellationToken = default);

    Task DeleteSnapshotRecordAsync(
        string snapshotId,
        CancellationToken cancellationToken = default);

    Task<SnapshotSlotRecord?> ResolveSlotAsync(
        string projectId,
        SnapshotSlotKind kind,
        string key,
        CancellationToken cancellationToken = default);

    Task MigrateLegacyRepositoryAsync(
        string legacyRepositoryId,
        string projectId,
        CancellationToken cancellationToken = default);

    Task<SnapshotSlotMutationResult> UpsertRetainedSlotAsync(
        string projectId,
        SnapshotSlotKind kind,
        string key,
        string snapshotId,
        long? expectedVersion,
        CancellationToken cancellationToken = default);

    Task<SnapshotSlotMutationResult> DeleteSlotAsync(
        string projectId,
        SnapshotSlotKind kind,
        string key,
        long? expectedVersion,
        TimeSpan unreferencedGracePeriod,
        CancellationToken cancellationToken = default);
}

public interface IStoreHealthCheck
{
    string Name { get; }

    Task<ComponentHealth> CheckAsync(CancellationToken cancellationToken = default);
}
