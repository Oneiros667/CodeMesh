using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;
using CodeMesh.Storage;

namespace CodeMesh.Ingestion.Summary;

public sealed record CodeSummaryGenerationOptions(
    string PromptVersion = SummaryPrompt.DefaultPromptVersion,
    int MaxInputCharacters = 4000,
    bool Force = false);

public sealed record CodeSummaryGenerationResult(
    int CandidateCount,
    int WrittenCount,
    int SkippedCount,
    int FailedCount,
    IReadOnlyList<CodeNodeSummary> Summaries);

public sealed class CodeSummaryGenerator(
    ICodeSummaryProvider provider,
    INodeSummaryStore summaryStore,
    CodeSummaryGenerationOptions? options = null)
{
    private readonly CodeSummaryGenerationOptions _options = options ?? new CodeSummaryGenerationOptions();

    public async Task<CodeSummaryGenerationResult> GenerateAsync(
        RepositoryRef repository,
        string ingestionRunId,
        IReadOnlyList<CodeNode> nodes,
        IReadOnlyDictionary<string, CodeContent> contentByHash,
        CancellationToken cancellationToken = default)
    {
        var candidates = nodes
            .Where(IsSummaryCandidate)
            .ToArray();
        var currentSummaryIds = candidates
            .Select(node => SummaryId(repository.Id, node, SummaryKind(node), provider.Provider, provider.Model, _options.PromptVersion))
            .ToHashSet(StringComparer.Ordinal);
        var nodesToSummarize = candidates;
        var skippedCount = 0;

        if (!_options.Force && summaryStore is IIncrementalNodeSummaryStore incrementalStore)
        {
            var existing = await incrementalStore
                .GetSummaryStatesAsync(repository.Id, cancellationToken)
                .ConfigureAwait(false);
            var existingKeys = existing
                .Where(summary =>
                    string.Equals(summary.Provider, provider.Provider, StringComparison.Ordinal) &&
                    string.Equals(summary.Model, provider.Model, StringComparison.Ordinal) &&
                    string.Equals(summary.PromptVersion, _options.PromptVersion, StringComparison.Ordinal) &&
                    string.Equals(summary.Status, "completed", StringComparison.Ordinal))
                .Select(summary => SummaryLookupKey(summary.NodeId, summary.ContentHash, summary.SummaryKind))
                .ToHashSet(StringComparer.Ordinal);

            nodesToSummarize = candidates
                .Where(node => !existingKeys.Contains(SummaryLookupKey(node.Id, node.ContentHash, SummaryKind(node))))
                .ToArray();
            skippedCount = candidates.Length - nodesToSummarize.Length;
        }

        var summaries = new List<CodeNodeSummary>(nodesToSummarize.Length);
        foreach (var node in nodesToSummarize)
        {
            cancellationToken.ThrowIfCancellationRequested();
            summaries.Add(await CreateSummaryAsync(repository, ingestionRunId, node, contentByHash, cancellationToken)
                .ConfigureAwait(false));
        }

        await summaryStore.UpsertSummariesAsync(summaries, cancellationToken)
            .ConfigureAwait(false);

        if (summaryStore is IIncrementalNodeSummaryStore cleanupStore)
        {
            await cleanupStore
                .RemoveSummariesExceptAsync(repository.Id, currentSummaryIds, cancellationToken)
                .ConfigureAwait(false);
        }

        var failedCount = summaries.Count(summary => string.Equals(summary.Status, "failed", StringComparison.Ordinal));

        return new CodeSummaryGenerationResult(
            candidates.Length,
            summaries.Count - failedCount,
            skippedCount,
            failedCount,
            summaries);
    }

    private async Task<CodeNodeSummary> CreateSummaryAsync(
        RepositoryRef repository,
        string ingestionRunId,
        CodeNode node,
        IReadOnlyDictionary<string, CodeContent> contentByHash,
        CancellationToken cancellationToken)
    {
        var summaryKind = SummaryKind(node);
        var id = SummaryId(repository.Id, node, summaryKind, provider.Provider, provider.Model, _options.PromptVersion);
        var generatedAt = DateTimeOffset.UtcNow;
        var metadata = MetadataFor(node, repository, ingestionRunId);
        contentByHash.TryGetValue(node.ContentHash, out var content);

        try
        {
            var result = await provider
                .SummarizeAsync(
                    new CodeSummaryRequest(node, content, _options.PromptVersion, Math.Max(512, _options.MaxInputCharacters)),
                    cancellationToken)
                .ConfigureAwait(false);

            return new CodeNodeSummary(
                id,
                repository.Id,
                repository.RootPath,
                ingestionRunId,
                node.Id,
                node.StableKey,
                node.Kind,
                node.Name,
                node.Language,
                node.Project,
                node.Span,
                node.ContentHash,
                summaryKind,
                result.Summary,
                result.Tags,
                result.Confidence,
                provider.Provider,
                provider.Model,
                _options.PromptVersion,
                SummaryPrompt.PromptHash(_options.PromptVersion),
                generatedAt,
                "completed",
                null,
                metadata);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return new CodeNodeSummary(
                id,
                repository.Id,
                repository.RootPath,
                ingestionRunId,
                node.Id,
                node.StableKey,
                node.Kind,
                node.Name,
                node.Language,
                node.Project,
                node.Span,
                node.ContentHash,
                summaryKind,
                "",
                [],
                "low",
                provider.Provider,
                provider.Model,
                _options.PromptVersion,
                SummaryPrompt.PromptHash(_options.PromptVersion),
                generatedAt,
                "failed",
                exception.Message,
                metadata);
        }
    }

    public static string SummaryId(
        string repositoryId,
        CodeNode node,
        string summaryKind,
        string provider,
        string model,
        string promptVersion)
    {
        return CodeMeshHash.StableId(
            "summary",
            repositoryId,
            node.Id,
            node.ContentHash,
            summaryKind,
            provider,
            model,
            promptVersion);
    }

    private static bool IsSummaryCandidate(CodeNode node)
    {
        return node.Kind is
            CodeNodeKind.File or
            CodeNodeKind.Class or
            CodeNodeKind.Interface or
            CodeNodeKind.Struct or
            CodeNodeKind.Enum or
            CodeNodeKind.Delegate or
            CodeNodeKind.Method or
            CodeNodeKind.Constructor or
            CodeNodeKind.Property or
            CodeNodeKind.Event;
    }

    private static string SummaryKind(CodeNode node)
    {
        return node.Kind == CodeNodeKind.File ? "file" : "symbol";
    }

    private static string SummaryLookupKey(string nodeId, string contentHash, string summaryKind)
    {
        return $"{nodeId}\u001f{contentHash}\u001f{summaryKind}";
    }

    private static IReadOnlyDictionary<string, string> MetadataFor(
        CodeNode node,
        RepositoryRef repository,
        string ingestionRunId)
    {
        return new Dictionary<string, string>(node.Metadata, StringComparer.Ordinal)
        {
            ["repositoryId"] = repository.Id,
            ["repositoryRoot"] = repository.RootPath,
            ["ingestionRunId"] = ingestionRunId,
            ["summaryNodeKind"] = node.Kind.ToString(),
            ["summaryNodeName"] = node.Name
        };
    }
}
