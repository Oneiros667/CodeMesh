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

        var parseRequest = new ParseRequest(
            repositoryRoot,
            request.SolutionPath,
            request.ProjectPath,
            request.Language,
            request.Options ?? new Dictionary<string, string>());

        var parseResult = await parserClient.ParseAsync(parseRequest, cancellationToken)
            .ConfigureAwait(false);

        var batch = new CodeGraphBatch(
            CodeMeshHash.StableId(repository.Id, startedAt.ToUnixTimeMilliseconds().ToString()),
            repository,
            parseResult.Nodes,
            parseResult.Relationships,
            parseResult.Contents,
            DateTimeOffset.UtcNow);

        var embeddingCount = 0;

        if (!request.DryRun)
        {
            await graphStore.UpsertGraphAsync(batch, cancellationToken).ConfigureAwait(false);

            foreach (var content in batch.Contents)
            {
                await contentStore.UpsertContentAsync(content, cancellationToken).ConfigureAwait(false);
            }

            if (!request.SkipEmbeddings)
            {
                var contentByHash = batch.Contents
                    .GroupBy(content => content.Hash, StringComparer.Ordinal)
                    .ToDictionary(group => group.Key, group => group.First(), StringComparer.Ordinal);

                var embeddings = await embeddingProvider
                    .EmbedAsync(batch.Nodes, contentByHash, cancellationToken)
                    .ConfigureAwait(false);

                await vectorStore.UpsertEmbeddingsAsync(embeddings, cancellationToken)
                    .ConfigureAwait(false);

                embeddingCount = embeddings.Count;
            }
        }

        return new IngestionResult(
            new IngestionRun(
                CodeMeshHash.StableId(repository.Id, startedAt.ToString("O")),
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
}
