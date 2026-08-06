using CodeMesh.Domain.Graph;

namespace CodeMesh.Ingestion.Summary;

public sealed record CodeSummaryRequest(
    CodeNode Node,
    CodeContent? Content,
    string PromptVersion,
    int MaxInputCharacters,
    SummaryBudget? Budget = null);

public sealed record CodeSummaryResult(
    string Summary,
    IReadOnlyList<string> Tags,
    string Confidence,
    CodeSummaryUsage? Usage = null,
    IReadOnlyDictionary<string, string>? ProviderMetadata = null);

public sealed record CodeSummaryUsage(
    int InputTokens,
    int CachedInputTokens,
    int CacheWriteInputTokens,
    int OutputTokens,
    int ReasoningTokens,
    int TotalTokens);

public interface ICodeSummaryProvider
{
    string Provider { get; }

    string Model { get; }

    string GenerationConfigurationFingerprint => "";

    Task<CodeSummaryResult> SummarizeAsync(
        CodeSummaryRequest request,
        CancellationToken cancellationToken = default);
}
