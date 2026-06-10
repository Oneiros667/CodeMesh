using CodeMesh.Domain.Graph;
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
            .Where(CodeSummaryIdentity.IsCandidate)
            .ToArray();
        var currentSummaryIds = candidates
            .Select(node => CodeSummaryIdentity.SummaryId(
                repository.Id,
                node,
                CodeSummaryIdentity.SummaryKind(node),
                provider.Provider,
                provider.Model,
                _options.PromptVersion))
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
                .Select(summary => CodeSummaryIdentity.LookupKey(summary.NodeId, summary.ContentHash, summary.SummaryKind))
                .ToHashSet(StringComparer.Ordinal);

            nodesToSummarize = candidates
                .Where(node => !existingKeys.Contains(CodeSummaryIdentity.LookupKey(
                    node.Id,
                    node.ContentHash,
                    CodeSummaryIdentity.SummaryKind(node))))
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
        var summaryKind = CodeSummaryIdentity.SummaryKind(node);
        var id = CodeSummaryIdentity.SummaryId(
            repository.Id,
            node,
            summaryKind,
            provider.Provider,
            provider.Model,
            _options.PromptVersion);
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
