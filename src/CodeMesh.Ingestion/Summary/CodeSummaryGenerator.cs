using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;
using CodeMesh.Storage;

namespace CodeMesh.Ingestion.Summary;

public sealed record CodeSummaryGenerationOptions(
    string PromptVersion = SummaryPrompt.DefaultPromptVersion,
    int MaxInputCharacters = 4000,
    int ReasoningTokenReserve = 768,
    int MaxCompletionTokens = 1536,
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
        var generationConfigurationFingerprint = GenerationConfigurationFingerprint();
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
                _options.PromptVersion,
                generationConfigurationFingerprint))
            .ToHashSet(StringComparer.Ordinal);
        var nodesToSummarize = candidates;
        var skippedCount = 0;
        IReadOnlyList<StoredNodeSummaryState> existingSummaries = [];
        var incrementalStore = summaryStore as IIncrementalNodeSummaryStore;

        if (incrementalStore is not null)
        {
            existingSummaries = await incrementalStore
                .GetSummaryStatesAsync(repository.Id, cancellationToken)
                .ConfigureAwait(false);
        }

        if (!_options.Force && incrementalStore is not null)
        {
            var completedSummaryIds = existingSummaries
                .Where(summary => string.Equals(summary.Status, "completed", StringComparison.Ordinal))
                .Select(summary => summary.SummaryId)
                .ToHashSet(StringComparer.Ordinal);

            nodesToSummarize = candidates
                .Where(node => !completedSummaryIds.Contains(CodeSummaryIdentity.SummaryId(
                    repository.Id,
                    node,
                    CodeSummaryIdentity.SummaryKind(node),
                    provider.Provider,
                    provider.Model,
                    _options.PromptVersion,
                    generationConfigurationFingerprint)))
                .ToArray();
            skippedCount = candidates.Length - nodesToSummarize.Length;
        }

        var summaries = new List<CodeNodeSummary>(nodesToSummarize.Length);
        foreach (var node in nodesToSummarize)
        {
            cancellationToken.ThrowIfCancellationRequested();
            summaries.Add(await CreateSummaryAsync(
                    repository,
                    ingestionRunId,
                    node,
                    contentByHash,
                    generationConfigurationFingerprint,
                    cancellationToken)
                .ConfigureAwait(false));
        }

        await summaryStore.UpsertSummariesAsync(summaries, cancellationToken)
            .ConfigureAwait(false);

        if (incrementalStore is not null)
        {
            var currentSummaryKeys = candidates
                .Select(node => CodeSummaryIdentity.LookupKey(
                    node.Id,
                    node.ContentHash,
                    CodeSummaryIdentity.SummaryKind(node)))
                .ToHashSet(StringComparer.Ordinal);
            var retainedSummaryIds = existingSummaries
                .Where(summary =>
                    currentSummaryKeys.Contains(CodeSummaryIdentity.LookupKey(
                        summary.NodeId,
                        summary.ContentHash,
                        summary.SummaryKind)) &&
                    (!string.Equals(summary.Provider, provider.Provider, StringComparison.Ordinal) ||
                     !string.Equals(summary.Model, provider.Model, StringComparison.Ordinal) ||
                     !string.Equals(summary.PromptVersion, _options.PromptVersion, StringComparison.Ordinal) ||
                     currentSummaryIds.Contains(summary.SummaryId)))
                .Select(summary => summary.SummaryId)
                .Concat(currentSummaryIds)
                .ToHashSet(StringComparer.Ordinal);

            await incrementalStore
                .RemoveSummariesExceptAsync(repository.Id, retainedSummaryIds, cancellationToken)
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
        string generationConfigurationFingerprint,
        CancellationToken cancellationToken)
    {
        var summaryKind = CodeSummaryIdentity.SummaryKind(node);
        var id = CodeSummaryIdentity.SummaryId(
            repository.Id,
            node,
            summaryKind,
            provider.Provider,
            provider.Model,
            _options.PromptVersion,
            generationConfigurationFingerprint);
        var generatedAt = DateTimeOffset.UtcNow;
        contentByHash.TryGetValue(node.ContentHash, out var content);
        var request = SummaryBudgetPolicy.CreateRequest(
            node,
            content,
            _options.PromptVersion,
            new SummaryBudgetPolicyOptions(
                _options.MaxInputCharacters,
                _options.ReasoningTokenReserve,
                _options.MaxCompletionTokens));
        var metadata = MetadataFor(
            node,
            repository,
            ingestionRunId,
            request,
            generationConfigurationFingerprint);

        try
        {
            var result = await provider
                .SummarizeAsync(request, cancellationToken)
                .ConfigureAwait(false);
            var completedMetadata = MetadataWithProviderResult(metadata, result);

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
                generationConfigurationFingerprint,
                SummaryPrompt.PromptHash(_options.PromptVersion),
                generatedAt,
                "completed",
                null,
                completedMetadata);
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
                generationConfigurationFingerprint,
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
        string ingestionRunId,
        CodeSummaryRequest request,
        string generationConfigurationFingerprint)
    {
        var budget = request.Budget
            ?? throw new InvalidOperationException("Generated summaries require a summary budget.");

        return new Dictionary<string, string>(node.Metadata, StringComparer.Ordinal)
        {
            ["repositoryId"] = repository.Id,
            ["repositoryRoot"] = repository.RootPath,
            ["ingestionRunId"] = ingestionRunId,
            ["summaryNodeKind"] = node.Kind.ToString(),
            ["summaryNodeName"] = node.Name,
            ["summaryGenerationConfigurationFingerprint"] = generationConfigurationFingerprint,
            ["summaryBudgetPolicyVersion"] = budget.PolicyVersion,
            ["summaryComplexityTier"] = budget.ComplexityTier.ToString().ToLowerInvariant(),
            ["summaryVisibleTokenBudget"] = budget.VisibleTokenBudget.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["summaryReasoningTokenReserve"] = budget.ReasoningTokenReserve.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["summaryMaxCompletionTokens"] = budget.MaxCompletionTokens.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["summaryInputCharacters"] = budget.InputCharacters.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["summaryInputTruncated"] = budget.InputTruncated.ToString().ToLowerInvariant()
        };
    }

    private static IReadOnlyDictionary<string, string> MetadataWithProviderResult(
        IReadOnlyDictionary<string, string> metadata,
        CodeSummaryResult result)
    {
        if (result.Usage is null && result.ProviderMetadata is null)
        {
            return metadata;
        }

        var completed = new Dictionary<string, string>(metadata, StringComparer.Ordinal);
        if (result.Usage is { } usage)
        {
            completed["summaryInputTokens"] = usage.InputTokens.ToString(System.Globalization.CultureInfo.InvariantCulture);
            completed["summaryCachedInputTokens"] = usage.CachedInputTokens.ToString(System.Globalization.CultureInfo.InvariantCulture);
            completed["summaryCacheWriteInputTokens"] = usage.CacheWriteInputTokens.ToString(System.Globalization.CultureInfo.InvariantCulture);
            completed["summaryOutputTokens"] = usage.OutputTokens.ToString(System.Globalization.CultureInfo.InvariantCulture);
            completed["summaryReasoningTokens"] = usage.ReasoningTokens.ToString(System.Globalization.CultureInfo.InvariantCulture);
            completed["summaryTotalTokens"] = usage.TotalTokens.ToString(System.Globalization.CultureInfo.InvariantCulture);
        }

        if (result.ProviderMetadata is not null)
        {
            foreach (var item in result.ProviderMetadata)
            {
                completed[item.Key] = item.Value;
            }
        }

        return completed;
    }

    private string GenerationConfigurationFingerprint()
    {
        return CodeMeshHash.StableId(
            "summary-generation-configuration",
            SummaryBudgetPolicy.PolicyVersion,
            _options.MaxInputCharacters.ToString(System.Globalization.CultureInfo.InvariantCulture),
            _options.ReasoningTokenReserve.ToString(System.Globalization.CultureInfo.InvariantCulture),
            _options.MaxCompletionTokens.ToString(System.Globalization.CultureInfo.InvariantCulture),
            provider.GenerationConfigurationFingerprint);
    }
}
