using CodeMesh.Domain.Graph;

namespace CodeMesh.Ingestion.Summary;

public enum SummaryComplexityTier
{
    Compact,
    Standard,
    Complex,
    Aggregate
}

public sealed record SummaryBudget(
    string PolicyVersion,
    SummaryComplexityTier ComplexityTier,
    int VisibleTokenBudget,
    int ReasoningTokenReserve,
    int MaxCompletionTokens,
    int InputCharacters,
    bool InputTruncated);

public sealed record SummaryBudgetPolicyOptions(
    int MaxInputCharacters = 4000,
    int ReasoningTokenReserve = 768,
    int MaxCompletionTokens = 1536);

public static class SummaryBudgetPolicy
{
    public const string PolicyVersion = "summary-budget-v1";

    public static CodeSummaryRequest CreateRequest(
        CodeNode node,
        CodeContent? content,
        string promptVersion,
        SummaryBudgetPolicyOptions? options = null)
    {
        var configured = options ?? new SummaryBudgetPolicyOptions();
        Validate(configured);

        var sourceLength = content?.Text.Length ?? node.StableKey.Length;
        var inputCharacters = Math.Min(sourceLength, configured.MaxInputCharacters);
        var inputTruncated = sourceLength > configured.MaxInputCharacters;
        var tier = SelectTier(node, sourceLength, inputTruncated);
        var visibleTokenBudget = VisibleTokenBudget(tier);
        var tierCompletionFloor = tier is SummaryComplexityTier.Compact or SummaryComplexityTier.Standard
            ? 1024
            : 1536;
        var desiredCompletionTokens = Math.Max(
            tierCompletionFloor,
            visibleTokenBudget + configured.ReasoningTokenReserve);
        var maxCompletionTokens = Math.Max(
            visibleTokenBudget,
            Math.Min(configured.MaxCompletionTokens, desiredCompletionTokens));

        return new CodeSummaryRequest(
            node,
            content,
            promptVersion,
            configured.MaxInputCharacters,
            new SummaryBudget(
                PolicyVersion,
                tier,
                visibleTokenBudget,
                configured.ReasoningTokenReserve,
                maxCompletionTokens,
                inputCharacters,
                inputTruncated));
    }

    public static SummaryComplexityTier SelectTier(
        CodeNode node,
        int sourceLength,
        bool inputTruncated = false)
    {
        var kindTier = node.Kind switch
        {
            CodeNodeKind.File or CodeNodeKind.TestFile => SummaryComplexityTier.Aggregate,
            CodeNodeKind.Class or CodeNodeKind.Struct or CodeNodeKind.TestCase => SummaryComplexityTier.Complex,
            CodeNodeKind.Interface => SummaryComplexityTier.Standard,
            CodeNodeKind.Enum or
            CodeNodeKind.Delegate or
            CodeNodeKind.Method or
            CodeNodeKind.Constructor or
            CodeNodeKind.Property or
            CodeNodeKind.Event => SummaryComplexityTier.Compact,
            _ => SummaryComplexityTier.Standard
        };
        var lineCount = node.Span.StartLine > 0 && node.Span.EndLine >= node.Span.StartLine
            ? node.Span.EndLine - node.Span.StartLine + 1
            : 0;
        var sizeTier = inputTruncated || lineCount > 120 || sourceLength > 4000
            ? SummaryComplexityTier.Aggregate
            : lineCount > 40 || sourceLength > 2000
                ? SummaryComplexityTier.Complex
                : lineCount > 10 || sourceLength > 800
                    ? SummaryComplexityTier.Standard
                    : SummaryComplexityTier.Compact;
        var metadataTier = MetadataTier(node.Metadata);

        return (SummaryComplexityTier)Math.Max(
            (int)kindTier,
            Math.Max((int)sizeTier, (int)metadataTier));
    }

    public static int VisibleTokenBudget(SummaryComplexityTier tier)
    {
        return tier switch
        {
            SummaryComplexityTier.Compact => 128,
            SummaryComplexityTier.Standard => 192,
            SummaryComplexityTier.Complex => 320,
            SummaryComplexityTier.Aggregate => 448,
            _ => throw new ArgumentOutOfRangeException(nameof(tier), tier, null)
        };
    }

    private static SummaryComplexityTier MetadataTier(IReadOnlyDictionary<string, string> metadata)
    {
        var tier = SummaryComplexityTier.Compact;
        foreach (var key in new[] { "cyclomaticComplexity", "complexity", "branchCount" })
        {
            if (!metadata.TryGetValue(key, out var raw) || !int.TryParse(raw, out var value))
            {
                continue;
            }

            var candidate = value switch
            {
                > 20 => SummaryComplexityTier.Aggregate,
                > 10 => SummaryComplexityTier.Complex,
                > 3 => SummaryComplexityTier.Standard,
                _ => SummaryComplexityTier.Compact
            };
            tier = (SummaryComplexityTier)Math.Max((int)tier, (int)candidate);
        }

        return tier;
    }

    private static void Validate(SummaryBudgetPolicyOptions options)
    {
        if (options.MaxInputCharacters < 512)
        {
            throw new ArgumentOutOfRangeException(
                nameof(options),
                "Summary maximum input characters must be at least 512.");
        }

        if (options.ReasoningTokenReserve < 0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(options),
                "Summary reasoning token reserve cannot be negative.");
        }

        if (options.MaxCompletionTokens < VisibleTokenBudget(SummaryComplexityTier.Aggregate))
        {
            throw new ArgumentOutOfRangeException(
                nameof(options),
                $"Summary maximum completion tokens must be at least {VisibleTokenBudget(SummaryComplexityTier.Aggregate)}.");
        }
    }
}
