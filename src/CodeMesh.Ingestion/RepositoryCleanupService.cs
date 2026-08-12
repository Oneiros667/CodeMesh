using CodeMesh.Storage;

namespace CodeMesh.Ingestion;

public sealed record RepositoryCleanupResult(
    string RepositoryId,
    bool RegistryEntryExisted,
    bool GraphCleaned,
    bool ContentCleaned,
    bool EmbeddingsCleaned,
    bool SummariesCleaned);

public sealed class RepositoryCleanupService(
    IGraphStore graphStore,
    IContentStore contentStore,
    IVectorStore vectorStore,
    IRegistryStore registryStore,
    INodeSummaryStore? summaryStore = null)
{
    public async Task<RepositoryCleanupResult> DeleteRepositoryAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryId);

        var registryEntryExisted = await registryStore
            .GetRepositoryAsync(repositoryId, cancellationToken)
            .ConfigureAwait(false) is not null;

        var storageRepositoryIds = registryStore is ISnapshotRegistryStore snapshotRegistry
            ? (await snapshotRegistry.ListSnapshotsAsync(repositoryId, cancellationToken).ConfigureAwait(false))
                .Select(snapshot => snapshot.SnapshotId)
                .Append(repositoryId)
                .Distinct(StringComparer.Ordinal)
                .ToArray()
            : [repositoryId];

        var graphCleaned = false;
        if (graphStore is IIncrementalGraphStore incrementalGraphStore)
        {
            foreach (var storageRepositoryId in storageRepositoryIds)
            {
                await incrementalGraphStore
                    .RemoveGraphExceptAsync(
                        storageRepositoryId,
                        EmptySet(),
                        EmptySet(),
                        cancellationToken)
                    .ConfigureAwait(false);
            }
            graphCleaned = true;
        }
        else
        {
            throw new InvalidOperationException("The configured graph store does not support repository deletion.");
        }

        var contentCleaned = false;
        if (contentStore is IIncrementalContentStore incrementalContentStore)
        {
            foreach (var storageRepositoryId in storageRepositoryIds)
            {
                await incrementalContentStore
                    .RemoveContentExceptAsync(storageRepositoryId, EmptySet(), cancellationToken)
                    .ConfigureAwait(false);
            }
            contentCleaned = true;
        }
        else
        {
            throw new InvalidOperationException("The configured content store does not support repository deletion.");
        }

        var embeddingsCleaned = false;
        if (vectorStore is IIncrementalVectorStore incrementalVectorStore)
        {
            foreach (var storageRepositoryId in storageRepositoryIds)
            {
                await incrementalVectorStore
                    .RemoveEmbeddingsExceptAsync(storageRepositoryId, EmptySet(), cancellationToken)
                    .ConfigureAwait(false);
            }
            embeddingsCleaned = true;
        }
        else
        {
            throw new InvalidOperationException("The configured vector store does not support repository deletion.");
        }

        var summariesCleaned = false;
        if (summaryStore is not null)
        {
            if (summaryStore is IIncrementalNodeSummaryStore incrementalSummaryStore)
            {
                foreach (var storageRepositoryId in storageRepositoryIds)
                {
                    await incrementalSummaryStore
                        .RemoveSummariesExceptAsync(storageRepositoryId, EmptySet(), cancellationToken)
                        .ConfigureAwait(false);
                }
                summariesCleaned = true;
            }
            else
            {
                throw new InvalidOperationException("The configured summary store does not support repository deletion.");
            }
        }

        await registryStore
            .DeleteRepositoryAsync(repositoryId, cancellationToken)
            .ConfigureAwait(false);

        return new RepositoryCleanupResult(
            repositoryId,
            registryEntryExisted,
            graphCleaned,
            contentCleaned,
            embeddingsCleaned,
            summariesCleaned);
    }

    private static HashSet<string> EmptySet()
    {
        return new HashSet<string>(StringComparer.Ordinal);
    }
}
