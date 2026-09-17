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
    bool ForceEmbeddings = false,
    bool IncludeSummaries = false,
    bool ForceSummaries = false,
    IReadOnlyDictionary<string, string>? Options = null,
    int SummaryMaxInputCharacters = 4000,
    int SummaryReasoningTokenReserve = 768,
    int SummaryMaxCompletionTokens = 1536,
    string? ProjectId = null,
    int SnapshotRetentionGraceSeconds = 86400,
    RepositoryPathFilter? PathFilter = null);

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
    IReadOnlyList<ParserDiagnostic> Diagnostics,
    IngestionStats? Stats = null,
    int SummaryCount = 0);

public sealed record IngestionStats(
    int ParsedNodeCount,
    int WrittenNodeCount,
    int SkippedNodeCount,
    int ParsedRelationshipCount,
    int WrittenRelationshipCount,
    int SkippedRelationshipCount,
    int ParsedContentCount,
    int WrittenContentCount,
    int SkippedContentCount,
    int WrittenEmbeddingCount,
    int SkippedEmbeddingCount,
    int SummaryCandidateCount = 0,
    int WrittenSummaryCount = 0,
    int SkippedSummaryCount = 0,
    int FailedSummaryCount = 0);

public sealed record RepositoryIndexRecord(
    string RepositoryId,
    string RootPath,
    string? RemoteUrl,
    string? Branch,
    string? Commit,
    DateTimeOffset FirstSeenAt,
    DateTimeOffset LastSeenAt,
    string? LastRunId,
    IngestionStage? LastStage,
    string? LastMessage,
    int NodeCount,
    int RelationshipCount,
    int ContentCount,
    int? EmbeddingCount,
    IReadOnlyDictionary<string, string> Metadata,
    string? Alias = null);

public sealed record IngestionRunIndexRecord(
    string RunId,
    string RepositoryId,
    string RepositoryRoot,
    IngestionStage Stage,
    DateTimeOffset StartedAt,
    DateTimeOffset? FinishedAt,
    string? Message,
    string Language,
    string ParserName,
    string? SolutionPath,
    string? ProjectPath,
    bool DryRun,
    bool SkipEmbeddings,
    string EmbeddingProvider,
    string EmbeddingModel,
    int NodeCount,
    int RelationshipCount,
    int ContentCount,
    int EmbeddingCount,
    IngestionStats? Stats,
    int DiagnosticCount,
    int ErrorDiagnosticCount,
    int WarningDiagnosticCount,
    IReadOnlyDictionary<string, string> Metadata);

public interface IIngestionOrchestrator
{
    Task<IngestionResult> IngestAsync(IngestionRequest request, CancellationToken cancellationToken = default);
}
