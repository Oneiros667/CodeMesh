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
    IEmbeddingProvider embeddingProvider) : IIngestionOrchestrator
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
        var batch = new CodeGraphBatch(
            ingestionRunId,
            repository,
            nodes,
            relationships,
            parseResult.Contents,
            seenAt);

        var embeddingCount = 0;

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
                var contentByHash = batch.Contents
                    .GroupBy(content => content.Hash, StringComparer.Ordinal)
                    .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);

                var embeddings = await embeddingProvider
                    .EmbedAsync(batch.Nodes, contentByHash, cancellationToken)
                    .ConfigureAwait(false);
                embeddings = StampEmbeddings(embeddings, repository, ingestionRunId, seenAt);

                await vectorStore.UpsertEmbeddingsAsync(embeddings, cancellationToken)
                    .ConfigureAwait(false);

                embeddingCount = embeddings.Count;
            }

            if (graphStore is IRefreshableGraphStore refreshableGraphStore)
            {
                await refreshableGraphStore
                    .RemoveStaleGraphAsync(repository.Id, ingestionRunId, cancellationToken)
                    .ConfigureAwait(false);
            }

            if (contentStore is IRefreshableContentStore cleanupContentStore)
            {
                await cleanupContentStore
                    .RemoveStaleContentAsync(repository.Id, ingestionRunId, cancellationToken)
                    .ConfigureAwait(false);
            }

            if (!request.SkipEmbeddings && vectorStore is IRefreshableVectorStore refreshableVectorStore)
            {
                await refreshableVectorStore
                    .RemoveStaleEmbeddingsAsync(repository.Id, ingestionRunId, cancellationToken)
                    .ConfigureAwait(false);
            }
        }

        return new IngestionResult(
            new IngestionRun(
                ingestionRunId,
                IngestionStage.Completed,
                startedAt,
                DateTimeOffset.UtcNow,
                request.DryRun ? "Dry run completed; no stores were written." : "Ingestion completed."),
            repository,
            batch.Nodes.Count,
            batch.Relationships.Count,
            batch.Contents.Count,
            embeddingCount,
            parseResult.Diagnostics);
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
