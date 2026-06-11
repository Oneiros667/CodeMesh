using System.Text.RegularExpressions;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Parser.Python;

public sealed partial class PythonParseService
{
    private static readonly HashSet<string> ExcludedDirectories = new(StringComparer.OrdinalIgnoreCase)
    {
        ".git",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "bin",
        "build",
        "dist",
        "node_modules",
        "obj",
        "venv"
    };

    public static ParserCapability Capability { get; } = new(
        "codemesh-parser-python",
        "python",
        "0.1.0",
        [".py"],
        ["repositoryRoot"]);

    public async Task<ParseResult> ParseAsync(
        ParseRequest request,
        CancellationToken cancellationToken = default)
    {
        var repositoryRoot = Path.GetFullPath(request.RepositoryRoot);
        if (!Directory.Exists(repositoryRoot))
        {
            return Failure(request, $"Repository root not found: {repositoryRoot}");
        }

        var nodes = new List<CodeNode>();
        var relationships = new List<CodeRelationship>();
        var contents = new List<CodeContent>();
        var diagnostics = new List<ParserDiagnostic>();
        var parsedAt = DateTimeOffset.UtcNow;

        foreach (var file in EnumeratePythonFiles(repositoryRoot))
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
                    "CMPY001",
                    $"Could not read Python file '{relativePath}': {exception.Message}",
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
        var fileHash = CodeMeshHash.Sha256Hex(text);
        var fileNodeId = $"python:file:{relativePath}";
        var fileNode = new CodeNode(
            fileNodeId,
            fileNodeId,
            CodeNodeKind.File,
            Path.GetFileName(relativePath),
            "python",
            ProjectName(repositoryRoot),
            new SourceSpan(relativePath, 1, 1, Math.Max(1, CountLines(text)), 1),
            fileHash,
            new Dictionary<string, string>
            {
                ["filePath"] = relativePath,
                ["module"] = ModuleName(relativePath)
            });
        nodes.Add(fileNode);
        contents.Add(new CodeContent(fileHash, text, "text/x-python", parsedAt, parsedAt));

        var lines = text.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
        var stack = new List<PythonScope> { new(fileNodeId, string.Empty, -1, CodeNodeKind.File) };
        for (var lineIndex = 0; lineIndex < lines.Length; lineIndex++)
        {
            var line = lines[lineIndex];
            var match = DefinitionRegex().Match(line);
            if (!match.Success)
            {
                continue;
            }

            var indent = match.Groups["indent"].Value.Length;
            while (stack.Count > 1 && stack[^1].Indent >= indent)
            {
                stack.RemoveAt(stack.Count - 1);
            }

            var name = match.Groups["name"].Value;
            var kindText = match.Groups["kind"].Value;
            var nodeKind = string.Equals(kindText, "class", StringComparison.Ordinal)
                ? CodeNodeKind.Class
                : CodeNodeKind.Method;
            var parent = stack[^1];
            var qualifiedName = string.IsNullOrWhiteSpace(parent.QualifiedName)
                ? name
                : $"{parent.QualifiedName}.{name}";
            var nodeId = $"python:{nodeKind.ToString().ToLowerInvariant()}:{ModuleName(relativePath)}.{qualifiedName}";
            var content = ExtractBlock(lines, lineIndex, indent);
            var contentHash = CodeMeshHash.Sha256Hex(content);
            var startLine = lineIndex + 1;
            var endLine = startLine + Math.Max(0, CountLines(content) - 1);
            var node = new CodeNode(
                nodeId,
                nodeId,
                nodeKind,
                name,
                "python",
                ProjectName(repositoryRoot),
                new SourceSpan(relativePath, startLine, indent + 1, endLine, 1),
                contentHash,
                new Dictionary<string, string>
                {
                    ["filePath"] = relativePath,
                    ["module"] = ModuleName(relativePath),
                    ["qualifiedName"] = qualifiedName,
                    ["parentNodeId"] = parent.NodeId,
                    ["async"] = match.Groups["async"].Success.ToString()
                });
            nodes.Add(node);
            contents.Add(new CodeContent(contentHash, content, "text/x-python-fragment", parsedAt, parsedAt));
            relationships.Add(new CodeRelationship(
                CodeMeshHash.StableId("python", "contains", parent.NodeId, nodeId),
                parent.NodeId,
                nodeId,
                CodeRelationshipKind.Contains,
                null,
                new Dictionary<string, string> { ["filePath"] = relativePath }));
            stack.Add(new PythonScope(nodeId, qualifiedName, indent, nodeKind));
        }
    }

    private static ParseResult Failure(ParseRequest request, string message)
    {
        return new ParseResult(
            Capability.WorkerName,
            Capability.Language,
            Array.Empty<CodeNode>(),
            Array.Empty<CodeRelationship>(),
            Array.Empty<CodeContent>(),
            [new ParserDiagnostic("CMPY000", message, "error")],
            DateTimeOffset.UtcNow);
    }

    private static IEnumerable<string> EnumeratePythonFiles(string repositoryRoot)
    {
        return Directory.EnumerateFiles(repositoryRoot, "*.py", SearchOption.AllDirectories)
            .Where(file => !IsExcluded(repositoryRoot, file))
            .OrderBy(file => file, StringComparer.OrdinalIgnoreCase);
    }

    private static bool IsExcluded(string repositoryRoot, string file)
    {
        var relativePath = Path.GetRelativePath(repositoryRoot, file);
        return relativePath
            .Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            .Any(segment => ExcludedDirectories.Contains(segment));
    }

    private static string ExtractBlock(string[] lines, int startIndex, int indent)
    {
        var endExclusive = startIndex + 1;
        for (; endExclusive < lines.Length; endExclusive++)
        {
            var line = lines[endExclusive];
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            if (LeadingSpaces(line) <= indent)
            {
                break;
            }
        }

        return string.Join(Environment.NewLine, lines[startIndex..endExclusive]);
    }

    private static int CountLines(string text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return 1;
        }

        return text.Count(character => character == '\n') + 1;
    }

    private static int LeadingSpaces(string line)
    {
        var count = 0;
        foreach (var character in line)
        {
            if (character == ' ')
            {
                count++;
                continue;
            }

            if (character == '\t')
            {
                count += 4;
                continue;
            }

            break;
        }

        return count;
    }

    private static string ProjectName(string repositoryRoot)
    {
        return new DirectoryInfo(repositoryRoot).Name;
    }

    private static string ModuleName(string relativePath)
    {
        return Path.ChangeExtension(relativePath, null)
            .Replace('\\', '.')
            .Replace('/', '.');
    }

    private static string NormalizePath(string path)
    {
        return path.Replace('\\', '/');
    }

    [GeneratedRegex(@"^(?<indent>\s*)(?:(?<async>async)\s+)?(?<kind>class|def)\s+(?<name>[A-Za-z_][A-Za-z0-9_]*)\b.*:\s*(?:#.*)?$")]
    private static partial Regex DefinitionRegex();

    private sealed record PythonScope(
        string NodeId,
        string QualifiedName,
        int Indent,
        CodeNodeKind Kind);
}
