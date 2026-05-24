using CodeMesh.Domain.Graph;

namespace CodeMesh.Ingestion.Embedding;

public sealed class NoEmbeddingProvider : IEmbeddingProvider
{
    public string Provider => "none";

    public string Model => "none";

    public Task<IReadOnlyList<EmbeddingRecord>> EmbedAsync(
        IReadOnlyList<CodeNode> nodes,
        IReadOnlyDictionary<string, CodeContent> contentByHash,
        CancellationToken cancellationToken = default)
    {
        return Task.FromResult<IReadOnlyList<EmbeddingRecord>>(Array.Empty<EmbeddingRecord>());
    }
}
