using CodeMesh.Domain.Graph;

namespace CodeMesh.Ingestion.Embedding;

public interface IEmbeddingProvider
{
    string Provider { get; }

    string Model { get; }

    Task<IReadOnlyList<EmbeddingRecord>> EmbedAsync(
        IReadOnlyList<CodeNode> nodes,
        IReadOnlyDictionary<string, CodeContent> contentByHash,
        CancellationToken cancellationToken = default);
}
