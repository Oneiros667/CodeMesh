using System.Text.Json;
using System.Text.Json.Serialization;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Ingestion.Summary;

public sealed record SummaryChatMessage(
    [property: JsonPropertyName("role")] string Role,
    [property: JsonPropertyName("content")] string Content);

internal static class SummaryPrompt
{
    public const string DefaultPromptVersion = "node-summary-v2";

    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public static IReadOnlyList<SummaryChatMessage> CreateMessages(CodeSummaryRequest request)
    {
        var source = request.Content?.Text ?? request.Node.StableKey;
        if (source.Length > request.MaxInputCharacters)
        {
            source = source[..request.MaxInputCharacters];
        }

        var system = """
You summarize source code for a code retrieval system.
Return only JSON with fields: summary, tags, confidence.
The summary must be factual, brief, and based only on the supplied code.
Use confidence high, medium, or low.
""";

        var budget = request.Budget ?? new SummaryBudget(
            SummaryBudgetPolicy.PolicyVersion,
            SummaryComplexityTier.Standard,
            SummaryBudgetPolicy.VisibleTokenBudget(SummaryComplexityTier.Standard),
            0,
            1024,
            source.Length,
            false);
        var instruction = budget.ComplexityTier switch
        {
            SummaryComplexityTier.Compact =>
                "Summarize this code node in one sentence. State only its essential responsibility.",
            SummaryComplexityTier.Standard =>
                "Summarize this code node in 1-2 sentences. State its responsibility and important behavior.",
            SummaryComplexityTier.Complex =>
                "Summarize this code node in 2-3 sentences. Cover its responsibility, important behavior, side effects, and failure behavior when present.",
            SummaryComplexityTier.Aggregate =>
                "Summarize this code node in 3-5 sentences. Cover its purpose, major responsibilities, and important integration boundaries.",
            _ => throw new ArgumentOutOfRangeException()
        };

        var user = $$"""
{{instruction}}
Keep the complete JSON response within approximately {{budget.VisibleTokenBudget}} visible tokens.

Node:
- kind: {{request.Node.Kind}}
- name: {{request.Node.Name}}
- language: {{request.Node.Language}}
- project: {{request.Node.Project}}
- file: {{request.Node.Span.FilePath}}
- lines: {{request.Node.Span.StartLine}}-{{request.Node.Span.EndLine}}
- summary complexity tier: {{budget.ComplexityTier.ToString().ToLowerInvariant()}}
- input truncated: {{budget.InputTruncated.ToString().ToLowerInvariant()}}

Code:
```{{request.Node.Language}}
{{source}}
```
""";

        return
        [
            new SummaryChatMessage("system", system),
            new SummaryChatMessage("user", user)
        ];
    }

    public static CodeSummaryResult ParseResult(string? content)
    {
        if (string.IsNullOrWhiteSpace(content))
        {
            throw new InvalidOperationException("Summary provider returned an empty response.");
        }

        try
        {
            var parsed = JsonSerializer.Deserialize<SummaryResponse>(ExtractJson(content), JsonOptions)
                ?? throw new InvalidOperationException("Summary provider returned invalid JSON.");
            var summary = parsed.Summary?.Trim();
            if (string.IsNullOrWhiteSpace(summary))
            {
                throw new InvalidOperationException("Summary provider returned JSON without a summary.");
            }

            var confidence = NormalizeConfidence(parsed.Confidence);
            var tags = (parsed.Tags ?? [])
                .Select(tag => tag.Trim())
                .Where(tag => !string.IsNullOrWhiteSpace(tag))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Take(8)
                .ToArray();

            return new CodeSummaryResult(summary, tags, confidence);
        }
        catch (JsonException exception)
        {
            throw new InvalidOperationException("Summary provider returned malformed JSON.", exception);
        }
    }

    public static string PromptHash(string promptVersion)
    {
        return CodeMeshHash.StableId("summary-prompt", promptVersion);
    }

    private static string ExtractJson(string content)
    {
        var trimmed = content.Trim();
        var start = trimmed.IndexOf('{');
        var end = trimmed.LastIndexOf('}');
        return start >= 0 && end >= start
            ? trimmed[start..(end + 1)]
            : trimmed;
    }

    private static string NormalizeConfidence(JsonElement? confidence)
    {
        if (confidence is not { } value)
        {
            return "medium";
        }

        if (value.ValueKind == JsonValueKind.Number &&
            value.TryGetDouble(out var score))
        {
            return score switch
            {
                >= 0.8 => "high",
                <= 0.4 => "low",
                _ => "medium"
            };
        }

        if (value.ValueKind != JsonValueKind.String)
        {
            return "medium";
        }

        var raw = value.GetString()?.Trim();
        if (double.TryParse(raw, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out score))
        {
            return score switch
            {
                >= 0.8 => "high",
                <= 0.4 => "low",
                _ => "medium"
            };
        }

        return raw?.ToLowerInvariant() switch
        {
            "high" => "high",
            "low" => "low",
            _ => "medium"
        };
    }

    private sealed record SummaryResponse(
        [property: JsonPropertyName("summary")] string? Summary,
        [property: JsonPropertyName("tags")] IReadOnlyList<string>? Tags,
        [property: JsonPropertyName("confidence")] JsonElement? Confidence);
}
