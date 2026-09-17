using System.Text.RegularExpressions;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Parser.Markdown;

public sealed partial class MarkdownParseService
{
    public static ParserCapability Capability { get; } = new(
        "codemesh-parser-markdown",
        "markdown",
        "0.1.1",
        [".md", ".markdown"],
        ["repositoryRoot", "pathFilter"]);

    public async Task<ParseResult> ParseAsync(
        ParseRequest request,
        CancellationToken cancellationToken = default)
    {
        var repositoryRoot = Path.GetFullPath(request.RepositoryRoot);
        if (!Directory.Exists(repositoryRoot))
        {
            return Failure($"Repository root not found: {repositoryRoot}");
        }

        var nodes = new List<CodeNode>();
        var relationships = new List<CodeRelationship>();
        var contents = new List<CodeContent>();
        var diagnostics = new List<ParserDiagnostic>();
        var parsedAt = DateTimeOffset.UtcNow;

        foreach (var file in EnumerateMarkdownFiles(repositoryRoot, request.PathFilter))
        {
            cancellationToken.ThrowIfCancellationRequested();
            var relativePath = NormalizePath(Path.GetRelativePath(repositoryRoot, file));
            try
            {
                var text = await File.ReadAllTextAsync(file, cancellationToken).ConfigureAwait(false);
                ParseFile(repositoryRoot, relativePath, text, parsedAt, nodes, relationships, contents);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                diagnostics.Add(new ParserDiagnostic(
                    "CMMD001",
                    $"Could not read Markdown file '{relativePath}': {exception.Message}",
                    "warning",
                    SourceSpan.Unknown(relativePath)));
            }
        }

        return new ParseResult(
            Capability.WorkerName,
            Capability.Language,
            nodes,
            relationships,
            contents,
            diagnostics,
            parsedAt);
    }

    private static void ParseFile(
        string repositoryRoot,
        string relativePath,
        string text,
        DateTimeOffset parsedAt,
        List<CodeNode> nodes,
        List<CodeRelationship> relationships,
        List<CodeContent> contents)
    {
        var documentHash = CodeMeshHash.Sha256Hex(text);
        var documentNodeId = $"markdown:document:{relativePath}";
        var document = new CodeNode(
            documentNodeId,
            documentNodeId,
            CodeNodeKind.Document,
            Path.GetFileName(relativePath),
            "markdown",
            ProjectName(repositoryRoot),
            new SourceSpan(relativePath, 1, 1, Math.Max(1, CountLines(text)), 1),
            documentHash,
            new Dictionary<string, string>
            {
                ["filePath"] = relativePath,
                ["documentKind"] = "Markdown"
            });
        nodes.Add(document);
        contents.Add(new CodeContent(documentHash, text, "text/markdown", parsedAt, parsedAt));

        var lines = text.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
        var headings = FindHeadings(lines).ToArray();
        var stack = new List<MarkdownScope> { new(documentNodeId, 0) };
        for (var index = 0; index < headings.Length; index++)
        {
            var heading = headings[index];
            while (stack.Count > 1 && stack[^1].Level >= heading.Level)
            {
                stack.RemoveAt(stack.Count - 1);
            }

            var endLine = index + 1 < headings.Length
                ? headings[index + 1].LineNumber - 1
                : lines.Length;
            var sectionText = string.Join(Environment.NewLine, lines[(heading.LineNumber - 1)..endLine]);
            var sectionHash = CodeMeshHash.Sha256Hex(sectionText);
            var anchor = AnchorFor(heading.Title);
            var sectionNodeId = $"markdown:section:{relativePath}#{anchor}";
            var section = new CodeNode(
                sectionNodeId,
                sectionNodeId,
                CodeNodeKind.Section,
                heading.Title,
                "markdown",
                ProjectName(repositoryRoot),
                new SourceSpan(relativePath, heading.LineNumber, 1, Math.Max(heading.LineNumber, endLine), 1),
                sectionHash,
                new Dictionary<string, string>
                {
                    ["filePath"] = relativePath,
                    ["documentKind"] = "Markdown",
                    ["headingLevel"] = heading.Level.ToString(),
                    ["anchor"] = anchor
                });
            nodes.Add(section);
            contents.Add(new CodeContent(sectionHash, sectionText, "text/markdown-fragment", parsedAt, parsedAt));

            var parent = stack[^1];
            relationships.Add(new CodeRelationship(
                CodeMeshHash.StableId("markdown", "contains", parent.NodeId, sectionNodeId),
                parent.NodeId,
                sectionNodeId,
                CodeRelationshipKind.Contains,
                null,
                new Dictionary<string, string>
                {
                    ["filePath"] = relativePath,
                    ["headingLevel"] = heading.Level.ToString()
                }));
            stack.Add(new MarkdownScope(sectionNodeId, heading.Level));
        }
    }

    private static IEnumerable<MarkdownHeading> FindHeadings(string[] lines)
    {
        for (var index = 0; index < lines.Length; index++)
        {
            var match = HeadingRegex().Match(lines[index]);
            if (!match.Success)
            {
                continue;
            }

            yield return new MarkdownHeading(
                match.Groups["marks"].Value.Length,
                match.Groups["title"].Value.Trim(),
                index + 1);
        }
    }

    private static ParseResult Failure(string message)
    {
        return new ParseResult(
            Capability.WorkerName,
            Capability.Language,
            Array.Empty<CodeNode>(),
            Array.Empty<CodeRelationship>(),
            Array.Empty<CodeContent>(),
            [new ParserDiagnostic("CMMD000", message, "error")],
            DateTimeOffset.UtcNow);
    }

    private static IEnumerable<string> EnumerateMarkdownFiles(
        string repositoryRoot,
        RepositoryPathFilter? pathFilter)
    {
        return RepositoryPathPolicy.EnumerateFiles(repositoryRoot, "*.*", pathFilter)
            .Where(IsMarkdownFile)
            .OrderBy(file => file, StringComparer.OrdinalIgnoreCase);
    }

    private static bool IsMarkdownFile(string file)
    {
        var extension = Path.GetExtension(file);
        return string.Equals(extension, ".md", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(extension, ".markdown", StringComparison.OrdinalIgnoreCase);
    }

    private static string AnchorFor(string title)
    {
        var lower = title.Trim().ToLowerInvariant();
        var anchor = AnchorCleanupRegex().Replace(lower, "");
        anchor = WhitespaceRegex().Replace(anchor, "-").Trim('-');
        return string.IsNullOrWhiteSpace(anchor) ? "section" : anchor;
    }

    private static int CountLines(string text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return 1;
        }

        return text.Count(character => character == '\n') + 1;
    }

    private static string ProjectName(string repositoryRoot)
    {
        return new DirectoryInfo(repositoryRoot).Name;
    }

    private static string NormalizePath(string path)
    {
        return path.Replace('\\', '/');
    }

    [GeneratedRegex(@"^(?<marks>#{1,6})\s+(?<title>.+?)\s*#*\s*$")]
    private static partial Regex HeadingRegex();

    [GeneratedRegex(@"[^\p{L}\p{Nd}\s-]")]
    private static partial Regex AnchorCleanupRegex();

    [GeneratedRegex(@"\s+")]
    private static partial Regex WhitespaceRegex();

    private sealed record MarkdownHeading(int Level, string Title, int LineNumber);

    private sealed record MarkdownScope(string NodeId, int Level);
}
