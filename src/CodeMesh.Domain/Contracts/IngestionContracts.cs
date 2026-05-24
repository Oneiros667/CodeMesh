using CodeMesh.Domain.Graph;

namespace CodeMesh.Domain.Contracts;

public enum IngestionStage
{
    Accepted,
    Parsing,
    Persisting,
    Embedding,
    Completed,
    Failed
}

public sealed record IngestionRequest(
    string RepositoryRoot,
    string? SolutionPath = null,
    string? ProjectPath = null,
    string Language = "csharp",
    bool DryRun = false,
    bool SkipEmbeddings = true,
    IReadOnlyDictionary<string, string>? Options = null);

public sealed record IngestionRun(
    string RunId,
    IngestionStage Stage,
    DateTimeOffset StartedAt,
    DateTimeOffset? FinishedAt,
    string? Message);

public sealed record IngestionResult(
    IngestionRun Run,
    RepositoryRef Repository,
    int NodeCount,
    int RelationshipCount,
    int ContentCount,
    int EmbeddingCount,
    IReadOnlyList<ParserDiagnostic> Diagnostics);

public interface IIngestionOrchestrator
{
    Task<IngestionResult> IngestAsync(IngestionRequest request, CancellationToken cancellationToken = default);
}
