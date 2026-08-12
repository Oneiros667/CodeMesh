using CodeMesh.Domain.Contracts;
using CodeMesh.Storage;

namespace CodeMesh.Ingestion;

public sealed record SnapshotGarbageCollectionResult(
    IReadOnlyList<string> DeletedSnapshotIds,
    IReadOnlyDictionary<string, string> Failures);

public sealed class SnapshotGarbageCollector(
    IGraphStore graphStore,
    IContentStore contentStore,
    IVectorStore vectorStore,
    ISnapshotRegistryStore registryStore,
    INodeSummaryStore? summaryStore = null)
{
    public async Task<SnapshotGarbageCollectionResult> CollectAsync(
        DateTimeOffset? now = null,
        CancellationToken cancellationToken = default)
    {
        var collectible = await registryStore
            .ListCollectibleSnapshotsAsync(now ?? DateTimeOffset.UtcNow, cancellationToken)
            .ConfigureAwait(false);
        var deleted = new List<string>();
        var failures = new Dictionary<string, string>(StringComparer.Ordinal);

        foreach (var snapshot in collectible)
        {
            try
            {
                await DeleteNamespaceAsync(snapshot.SnapshotId, cancellationToken).ConfigureAwait(false);
                await registryStore.DeleteSnapshotRecordAsync(snapshot.SnapshotId, cancellationToken)
                    .ConfigureAwait(false);
                deleted.Add(snapshot.SnapshotId);
            }
            catch (Exception exception) when (exception is not OperationCanceledException)
            {
                failures[snapshot.SnapshotId] = exception.Message;
            }
        }

        return new SnapshotGarbageCollectionResult(deleted, failures);
    }

    private async Task DeleteNamespaceAsync(string snapshotId, CancellationToken cancellationToken)
    {
        if (graphStore is not IIncrementalGraphStore graph ||
            contentStore is not IIncrementalContentStore content ||
            vectorStore is not IIncrementalVectorStore vectors ||
            summaryStore is not null and not IIncrementalNodeSummaryStore)
        {
            throw new InvalidOperationException("Every configured store must support reference-aware snapshot deletion.");
        }

        var empty = new HashSet<string>(StringComparer.Ordinal);
        await graph.RemoveGraphExceptAsync(snapshotId, empty, empty, cancellationToken).ConfigureAwait(false);
        await content.RemoveContentExceptAsync(snapshotId, empty, cancellationToken).ConfigureAwait(false);
        await vectors.RemoveEmbeddingsExceptAsync(snapshotId, empty, cancellationToken).ConfigureAwait(false);
        if (summaryStore is IIncrementalNodeSummaryStore summaries)
        {
            await summaries.RemoveSummariesExceptAsync(snapshotId, empty, cancellationToken).ConfigureAwait(false);
        }
    }
}
