using CodeMesh.Domain.Graph;

namespace CodeMesh.Ingestion.Summary;

public sealed record CodeSummaryRequest(
    CodeNode Node,
    CodeContent? Content,
    string PromptVersion,
    int MaxInputCharacters);

public sealed record CodeSummaryResult(
    string Summary,
    IReadOnlyList<string> Tags,
    string Confidence);

public interface ICodeSummaryProvider
{
    string Provider { get; }

    string Model { get; }

    Task<CodeSummaryResult> SummarizeAsync(
        CodeSummaryRequest request,
        CancellationToken cancellationToken = default);
}
