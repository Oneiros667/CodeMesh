using System.Text.RegularExpressions;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Parser.Python;

public sealed partial class PythonParseService
{
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
        var imports = ParseImports(
            repositoryRoot,
            relativePath,
            lines,
            fileNodeId,
            parsedAt,
            nodes,
            relationships,
            contents);
        var stack = new List<PythonScope>
        {
            new(fileNodeId, string.Empty, -1, CodeNodeKind.File, 1, 1, Math.Max(1, lines.Length), Path.GetFileName(relativePath))
        };
        var scopes = new List<PythonScope>();
        for (var lineIndex = 0; lineIndex < lines.Length; lineIndex++)
        {
            var line = lines[lineIndex];
            var match = MatchDefinition(lines, lineIndex, out var headerEndIndex);
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
                : IsTestFunction(name, Decorators(lines, lineIndex))
                    ? CodeNodeKind.TestCase
                    : CodeNodeKind.Method;
            var parent = stack[^1];
            var qualifiedName = string.IsNullOrWhiteSpace(parent.QualifiedName)
                ? name
                : $"{parent.QualifiedName}.{name}";
            var nodeId = $"python:{nodeKind.ToString().ToLowerInvariant()}:{ModuleName(relativePath)}.{qualifiedName}";
            var content = ExtractBlock(lines, lineIndex, headerEndIndex, indent);
            var contentHash = CodeMeshHash.Sha256Hex(content);
            var startLine = lineIndex + 1;
            var endLine = startLine + Math.Max(0, CountLines(content) - 1);
            var metadata = new Dictionary<string, string>
            {
                ["filePath"] = relativePath,
                ["module"] = ModuleName(relativePath),
                ["qualifiedName"] = qualifiedName,
                ["parentNodeId"] = parent.NodeId,
                ["async"] = match.Groups["async"].Success.ToString(),
                ["decorators"] = string.Join(' ', Decorators(lines, lineIndex))
            };
            if (nodeKind == CodeNodeKind.TestCase)
            {
                metadata["testRole"] = "case";
                metadata["testFramework"] = "python";
            }
            var node = new CodeNode(
                nodeId,
                nodeId,
                nodeKind,
                name,
                "python",
                ProjectName(repositoryRoot),
                new SourceSpan(relativePath, startLine, indent + 1, endLine, 1),
                contentHash,
                metadata);
            nodes.Add(node);
            contents.Add(new CodeContent(contentHash, content, "text/x-python-fragment", parsedAt, parsedAt));
            relationships.Add(new CodeRelationship(
                CodeMeshHash.StableId("python", "contains", parent.NodeId, nodeId),
                parent.NodeId,
                nodeId,
                CodeRelationshipKind.Contains,
                null,
                new Dictionary<string, string> { ["filePath"] = relativePath }));
            var scope = new PythonScope(
                nodeId,
                qualifiedName,
                indent,
                nodeKind,
                startLine,
                headerEndIndex + 1,
                endLine,
                name);
            stack.Add(scope);
            scopes.Add(scope);
            lineIndex = headerEndIndex;
        }

        AddSemanticRelationships(
            relativePath,
            lines,
            fileNodeId,
            scopes,
            imports,
            relationships);
    }

    private static IReadOnlyList<PythonImport> ParseImports(
        string repositoryRoot,
        string relativePath,
        string[] lines,
        string fileNodeId,
        DateTimeOffset parsedAt,
        List<CodeNode> nodes,
        List<CodeRelationship> relationships,
        List<CodeContent> contents)
    {
        var imports = new List<PythonImport>();
        var seenImports = new HashSet<string>(StringComparer.Ordinal);
        for (var lineIndex = 0; lineIndex < lines.Length; lineIndex++)
        {
            var line = lines[lineIndex];
            var fromMatch = FromImportRegex().Match(line);
            var importMatch = ImportRegex().Match(line);
            if (!fromMatch.Success && !importMatch.Success)
            {
                continue;
            }

            var module = fromMatch.Success ? fromMatch.Groups["module"].Value : string.Empty;
            var items = (fromMatch.Success ? fromMatch.Groups["items"] : importMatch.Groups["items"])
                .Value
                .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            foreach (var item in items)
            {
                var parts = AliasRegex().Match(item);
                if (!parts.Success)
                {
                    continue;
                }
                var importedName = parts.Groups["name"].Value;
                var importedModule = fromMatch.Success ? module : importedName;
                var alias = parts.Groups["alias"].Success
                    ? parts.Groups["alias"].Value
                    : fromMatch.Success
                        ? importedName
                        : importedName.Split('.').First();
                var importKey = $"{importedModule}\0{importedName}\0{alias}";
                if (!seenImports.Add(importKey))
                {
                    continue;
                }
                var nodeId = $"python:import:{CodeMeshHash.StableId(relativePath, importedModule, importedName, alias)}";
                var content = line.Trim();
                var contentHash = CodeMeshHash.Sha256Hex(content);
                var node = new CodeNode(
                    nodeId,
                    nodeId,
                    CodeNodeKind.Declaration,
                    fromMatch.Success ? importedName : importedModule,
                    "python",
                    ProjectName(repositoryRoot),
                    new SourceSpan(relativePath, lineIndex + 1, LeadingSpaces(line) + 1, lineIndex + 1, line.Length + 1),
                    contentHash,
                    new Dictionary<string, string>
                    {
                        ["filePath"] = relativePath,
                        ["module"] = ModuleName(relativePath),
                        ["pythonKind"] = "import",
                        ["importModule"] = importedModule,
                        ["importedName"] = fromMatch.Success ? importedName : string.Empty,
                        ["alias"] = alias,
                        ["parentNodeId"] = fileNodeId
                    });
                nodes.Add(node);
                contents.Add(new CodeContent(contentHash, content, "text/x-python-fragment", parsedAt, parsedAt));
                relationships.Add(new CodeRelationship(
                    CodeMeshHash.StableId("python", "contains", fileNodeId, nodeId),
                    fileNodeId,
                    nodeId,
                    CodeRelationshipKind.Contains,
                    null,
                    new Dictionary<string, string> { ["filePath"] = relativePath }));
                imports.Add(new PythonImport(node, importedModule, fromMatch.Success ? importedName : null, alias));
            }
        }
        return imports;
    }

    private static void AddSemanticRelationships(
        string relativePath,
        string[] lines,
        string fileNodeId,
        IReadOnlyList<PythonScope> scopes,
        IReadOnlyList<PythonImport> imports,
        List<CodeRelationship> relationships)
    {
        var definitions = scopes
            .GroupBy(scope => scope.Name, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.ToArray(), StringComparer.Ordinal);
        var importsByAlias = imports
            .GroupBy(item => item.Alias, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.ToArray(), StringComparer.Ordinal);

        foreach (var item in imports)
        {
            var targetName = item.ImportedName ?? item.Module.Split('.').Last();
            if (definitions.TryGetValue(targetName, out var targets) && targets.Length == 1)
            {
                relationships.Add(PythonRelationship(
                    item.Node.Id,
                    targets[0].NodeId,
                    CodeRelationshipKind.References,
                    targetName,
                    relativePath));
            }
        }

        foreach (var scope in scopes.Where(scope => scope.Kind is CodeNodeKind.Method or CodeNodeKind.TestCase))
        {
            var startIndex = Math.Min(scope.HeaderEndLine, lines.Length);
            var count = Math.Max(0, Math.Min(scope.EndLine, lines.Length) - startIndex);
            var body = string.Join('\n', lines.Skip(startIndex).Take(count));
            foreach (Match call in CallRegex().Matches(body))
            {
                var owner = call.Groups["owner"].Success ? call.Groups["owner"].Value : null;
                var name = call.Groups["name"].Value;
                if (IgnoredCallNames.Contains(name))
                {
                    continue;
                }

                if (owner is null && definitions.TryGetValue(name, out var targets) && targets.Length == 1)
                {
                    relationships.Add(PythonRelationship(
                        scope.NodeId,
                        targets[0].NodeId,
                        CodeRelationshipKind.Invokes,
                        name,
                        relativePath));
                    continue;
                }

                var importAlias = owner ?? name;
                if (importsByAlias.TryGetValue(importAlias, out var imported) && imported.Length == 1)
                {
                    relationships.Add(PythonRelationship(
                        scope.NodeId,
                        imported[0].Node.Id,
                        CodeRelationshipKind.Invokes,
                        owner is null ? imported[0].ImportedName ?? name : name,
                        relativePath));
                }
            }
        }
    }

    private static CodeRelationship PythonRelationship(
        string sourceNodeId,
        string targetNodeId,
        CodeRelationshipKind kind,
        string label,
        string relativePath)
    {
        return new CodeRelationship(
            CodeMeshHash.StableId("python", kind.ToString(), sourceNodeId, targetNodeId, label),
            sourceNodeId,
            targetNodeId,
            kind,
            label,
            new Dictionary<string, string> { ["filePath"] = relativePath });
    }

    private static IReadOnlyList<string> Decorators(string[] lines, int definitionIndex)
    {
        var decorators = new List<string>();
        for (var index = definitionIndex - 1; index >= 0; index--)
        {
            var trimmed = lines[index].Trim();
            if (!trimmed.StartsWith('@'))
            {
                break;
            }
            decorators.Insert(0, trimmed);
        }
        return decorators;
    }

    private static bool IsTestFunction(string name, IReadOnlyList<string> decorators)
    {
        return name.StartsWith("test_", StringComparison.Ordinal) ||
            decorators.Any(decorator =>
                decorator.Contains("pytest", StringComparison.OrdinalIgnoreCase) ||
                decorator.Contains("unittest", StringComparison.OrdinalIgnoreCase));
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
        return RepositoryPathPolicy.IsIgnoredPath(repositoryRoot, file);
    }

    private static string ExtractBlock(
        string[] lines,
        int startIndex,
        int headerEndIndex,
        int indent)
    {
        var endExclusive = headerEndIndex + 1;
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

    private static Match MatchDefinition(
        string[] lines,
        int startIndex,
        out int headerEndIndex)
    {
        headerEndIndex = startIndex;
        var first = lines[startIndex];
        if (!DefinitionStartRegex().IsMatch(first))
        {
            return DefinitionRegex().Match(string.Empty);
        }

        var header = first.TrimEnd();
        var balance = DelimiterBalance(first);
        while ((balance > 0 || !HasHeaderTerminator(header)) &&
               headerEndIndex + 1 < lines.Length)
        {
            headerEndIndex++;
            var continuation = lines[headerEndIndex].Trim();
            header = $"{header} {continuation}";
            balance += DelimiterBalance(continuation);
            if (headerEndIndex - startIndex >= 100)
            {
                break;
            }
        }

        return DefinitionRegex().Match(header);
    }

    private static bool HasHeaderTerminator(string header)
    {
        var balance = 0;
        var quote = '\0';
        var escaped = false;
        foreach (var character in header)
        {
            if (escaped)
            {
                escaped = false;
                continue;
            }
            if (character == '\\' && quote != '\0')
            {
                escaped = true;
                continue;
            }
            if (character is '\'' or '"')
            {
                if (quote == character)
                {
                    quote = '\0';
                }
                else if (quote == '\0')
                {
                    quote = character;
                }
                continue;
            }
            if (quote != '\0')
            {
                continue;
            }
            balance += character switch
            {
                '(' or '[' or '{' => 1,
                ')' or ']' or '}' => -1,
                _ => 0
            };
            if (character == ':' && balance == 0)
            {
                return true;
            }
        }
        return false;
    }

    private static int DelimiterBalance(string line)
    {
        var balance = 0;
        var quote = '\0';
        var escaped = false;
        foreach (var character in line)
        {
            if (escaped)
            {
                escaped = false;
                continue;
            }
            if (character == '\\' && quote != '\0')
            {
                escaped = true;
                continue;
            }
            if (character is '\'' or '"')
            {
                if (quote == character)
                {
                    quote = '\0';
                }
                else if (quote == '\0')
                {
                    quote = character;
                }
                continue;
            }
            if (quote != '\0')
            {
                continue;
            }
            balance += character switch
            {
                '(' or '[' or '{' => 1,
                ')' or ']' or '}' => -1,
                _ => 0
            };
        }
        return balance;
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

    [GeneratedRegex(@"^(?<indent>\s*)(?:(?<async>async)\s+)?(?<kind>class|def)\s+(?<name>[A-Za-z_][A-Za-z0-9_]*)\b.*:.*$")]
    private static partial Regex DefinitionRegex();

    [GeneratedRegex(@"^\s*(?:(?:async)\s+)?(?:class|def)\s+[A-Za-z_][A-Za-z0-9_]*\b")]
    private static partial Regex DefinitionStartRegex();

    [GeneratedRegex(@"^\s*import\s+(?<items>[^#]+?)(?:\s*#.*)?$")]
    private static partial Regex ImportRegex();

    [GeneratedRegex(@"^\s*from\s+(?<module>[A-Za-z_][A-Za-z0-9_.]*)\s+import\s+(?<items>[^#]+?)(?:\s*#.*)?$")]
    private static partial Regex FromImportRegex();

    [GeneratedRegex(@"^(?<name>[A-Za-z_][A-Za-z0-9_.]*)(?:\s+as\s+(?<alias>[A-Za-z_][A-Za-z0-9_]*))?$")]
    private static partial Regex AliasRegex();

    [GeneratedRegex(@"(?<![A-Za-z0-9_])(?:(?<owner>[A-Za-z_][A-Za-z0-9_]*)\s*\.\s*)?(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")]
    private static partial Regex CallRegex();

    private static readonly HashSet<string> IgnoredCallNames = new(StringComparer.Ordinal)
    {
        "and", "assert", "async", "await", "class", "def", "del", "elif", "else", "except", "False", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "None", "nonlocal", "not", "or", "pass", "raise", "return", "True", "try", "while", "with", "yield"
    };

    private sealed record PythonScope(
        string NodeId,
        string QualifiedName,
        int Indent,
        CodeNodeKind Kind,
        int StartLine,
        int HeaderEndLine,
        int EndLine,
        string Name);

    private sealed record PythonImport(
        CodeNode Node,
        string Module,
        string? ImportedName,
        string Alias);
}
