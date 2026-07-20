using System.Text.RegularExpressions;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Ingestion;

public sealed record ContentRedactionResult(
    IReadOnlyList<CodeContent> Contents,
    IReadOnlyDictionary<string, string> ContentHashMap,
    int RedactedContentCount);

public static partial class ContentRedactor
{
    private const string RedactedValue = "<redacted>";

    public static ContentRedactionResult Redact(IReadOnlyList<CodeContent> contents)
    {
        var redactedContents = new List<CodeContent>(contents.Count);
        var hashMap = new Dictionary<string, string>(StringComparer.Ordinal);
        var redactedCount = 0;

        foreach (var content in contents)
        {
            var redactedText = RedactText(content.Text);
            if (string.Equals(redactedText, content.Text, StringComparison.Ordinal))
            {
                redactedContents.Add(content);
                hashMap[content.Hash] = content.Hash;
                continue;
            }

            var redactedHash = CodeMeshHash.Sha256Hex(redactedText);
            redactedContents.Add(content with
            {
                Hash = redactedHash,
                Text = redactedText,
                UpdatedAt = DateTimeOffset.UtcNow
            });
            hashMap[content.Hash] = redactedHash;
            redactedCount++;
        }

        return new ContentRedactionResult(redactedContents, hashMap, redactedCount);
    }

    public static string RedactText(string text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return text;
        }

        var redacted = PrivateKeyBlockRegex().Replace(text, match =>
        {
            var label = match.Groups["label"].Value;
            return $"-----BEGIN {label}-----\n{RedactedValue}\n-----END {label}-----";
        });
        redacted = KeyValueRegex().Replace(redacted, match =>
            $"{match.Groups["prefix"].Value}{RedactedValue}");
        redacted = JsonStringRegex().Replace(redacted, match =>
            $"{match.Groups["prefix"].Value}{RedactedValue}{match.Groups["quote"].Value}");
        redacted = CSharpAssignmentRegex().Replace(redacted, match =>
            $"{match.Groups["prefix"].Value}{RedactedValue}{match.Groups["quote"].Value}");
        redacted = QuotedKeyValueRegex().Replace(redacted, match =>
            $"{match.Groups["prefix"].Value}{RedactedValue}{match.Groups["quote"].Value}");
        redacted = ConnectionStringPasswordRegex().Replace(redacted, match =>
            $"{match.Groups["prefix"].Value}{RedactedValue}");

        return redacted;
    }

    public static IReadOnlyList<CodeNode> RemapNodeContentHashes(
        IReadOnlyList<CodeNode> nodes,
        IReadOnlyDictionary<string, string> contentHashMap)
    {
        return nodes
            .Select(node => contentHashMap.TryGetValue(node.ContentHash, out var redactedHash) &&
                            !string.Equals(redactedHash, node.ContentHash, StringComparison.Ordinal)
                ? node with { ContentHash = redactedHash }
                : node)
            .ToArray();
    }

    [GeneratedRegex(
        @"-----BEGIN (?<label>[A-Z0-9 ]*PRIVATE KEY)-----[\s\S]*?-----END \k<label>-----",
        RegexOptions.Compiled)]
    private static partial Regex PrivateKeyBlockRegex();

    [GeneratedRegex(
        @"(?im)^(?<prefix>\s*(?:[A-Z0-9_]*?(?:SECRET|PASSWORD|PASSWD|TOKEN|API[_-]?KEY|PRIVATE[_-]?KEY|CONNECTION[_-]?STRING)[A-Z0-9_]*?)\s*[:=]\s*)(?<value>.+)$",
        RegexOptions.Compiled)]
    private static partial Regex KeyValueRegex();

    [GeneratedRegex(
        @"(?i)(?<prefix>[""'](?:[^""']*(?:secret|password|passwd|token|api[_-]?key|private[_-]?key|connection[_-]?string)[^""']*)[""']\s*:\s*(?<quote>[""']))[^""'\r\n]*(?<end>\k<quote>)",
        RegexOptions.Compiled)]
    private static partial Regex JsonStringRegex();

    [GeneratedRegex(
        @"(?i)(?<prefix>\b(?:[A-Za-z0-9_]*?(?:secret|password|passwd|token|apiKey|api_key|privateKey|private_key|connectionString|connection_string)[A-Za-z0-9_]*)\b\s*=\s*(?<quote>[""']))[^""'\r\n]*(?<end>\k<quote>)",
        RegexOptions.Compiled)]
    private static partial Regex CSharpAssignmentRegex();

    [GeneratedRegex(
        @"(?i)(?<prefix>[""'][^""'\r\n]*\b[A-Z0-9_]*?(?:SECRET|PASSWORD|PASSWD|TOKEN|API[_-]?KEY|PRIVATE[_-]?KEY|CONNECTION[_-]?STRING)[A-Z0-9_]*?\s*[:=]\s*)[^""'\r\n]*(?<quote>[""'])",
        RegexOptions.Compiled)]
    private static partial Regex QuotedKeyValueRegex();

    [GeneratedRegex(
        @"(?i)(?<prefix>\b(?:Password|Pwd)\s*=\s*)[^;\r\n]+",
        RegexOptions.Compiled)]
    private static partial Regex ConnectionStringPasswordRegex();
}
