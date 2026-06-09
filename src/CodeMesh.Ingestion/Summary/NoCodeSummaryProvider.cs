namespace CodeMesh.Ingestion.Summary;

public sealed class NoCodeSummaryProvider : ICodeSummaryProvider
{
    public string Provider => "none";

    public string Model => "none";

    public Task<CodeSummaryResult> SummarizeAsync(
        CodeSummaryRequest request,
        CancellationToken cancellationToken = default)
    {
        throw new InvalidOperationException("Node summaries are disabled.");
    }
}
