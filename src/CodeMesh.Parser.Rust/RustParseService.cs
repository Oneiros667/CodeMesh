using System.Text.RegularExpressions;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Parser.Rust;

public sealed partial class RustParseService
{
    public static ParserCapability Capability { get; } = new(
        "codemesh-parser-rust",
        "rust",
        "0.1.1",
        [".rs"],
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

        foreach (var file in EnumerateRustFiles(repositoryRoot, request.PathFilter))
        {
            cancellationToken.ThrowIfCancellationRequested();
            var relativePath = NormalizePath(Path.GetRelativePath(repositoryRoot, file));
            try
            {
                var text = await File.ReadAllTextAsync(file, cancellationToken).ConfigureAwait(false);
                ParseFile(
                    repositoryRoot,
                    relativePath,
                    text,
                    parsedAt,
                    nodes,
                    relationships,
                    contents,
                    diagnostics);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                diagnostics.Add(new ParserDiagnostic(
                    "CMRS001",
                    $"Could not read Rust file '{relativePath}': {exception.Message}",
                    "warning",
                    SourceSpan.Unknown(relativePath)));
            }
        }

        return new ParseResult(
            Capability.WorkerName,
            Capability.Language,
            nodes,
            relationships,
            contents.GroupBy(content => content.Hash, StringComparer.Ordinal).Select(group => group.First()).ToArray(),
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
        List<CodeContent> contents,
        List<ParserDiagnostic> diagnostics)
    {
        var project = ProjectName(repositoryRoot);
        var module = ModuleName(relativePath);
        var lines = NormalizeLines(text);
        var fileHash = CodeMeshHash.Sha256Hex(text);
        var fileNodeId = $"rust:file:{relativePath}";
        var fileKind = IsTestFile(relativePath) ? CodeNodeKind.TestFile : CodeNodeKind.File;
        nodes.Add(new CodeNode(
            fileNodeId,
            fileNodeId,
            fileKind,
            Path.GetFileName(relativePath),
            "rust",
            project,
            new SourceSpan(relativePath, 1, 1, Math.Max(1, lines.Length), 1),
            fileHash,
            new Dictionary<string, string>
            {
                ["filePath"] = relativePath,
                ["module"] = module,
                ["rustKind"] = "file"
            }));
        contents.Add(new CodeContent(fileHash, text, "text/x-rust", parsedAt, parsedAt));

        var declarations = CollectDeclarations(lines, relativePath, diagnostics);
        var built = new List<BuiltDeclaration>();
        foreach (var declaration in declarations)
        {
            var parent = built
                .Where(candidate =>
                    candidate.Declaration.StartLine < declaration.StartLine &&
                    candidate.Declaration.EndLine >= declaration.EndLine &&
                    candidate.Declaration.HasBody)
                .OrderByDescending(candidate => candidate.Declaration.StartLine)
                .FirstOrDefault();
            var qualifiedName = parent is null
                ? declaration.Name
                : $"{parent.QualifiedName}::{declaration.Name}";
            var nodeId = NodeId(module, declaration, qualifiedName);
            var content = string.Join(
                Environment.NewLine,
                lines[(declaration.StartLine - 1)..declaration.EndLine]);
            var contentHash = CodeMeshHash.Sha256Hex(content);
            var metadata = DeclarationMetadata(relativePath, module, declaration, qualifiedName, parent?.Node.Id ?? fileNodeId);
            var node = new CodeNode(
                nodeId,
                nodeId,
                declaration.NodeKind,
                declaration.Name,
                "rust",
                project,
                new SourceSpan(
                    relativePath,
                    declaration.StartLine,
                    declaration.StartColumn,
                    declaration.EndLine,
                    1),
                contentHash,
                metadata);
            nodes.Add(node);
            contents.Add(new CodeContent(
                contentHash,
                content,
                "text/x-rust-fragment",
                parsedAt,
                parsedAt));
            relationships.Add(Relationship(
                parent?.Node.Id ?? fileNodeId,
                nodeId,
                CodeRelationshipKind.Contains,
                null,
                relativePath));
            built.Add(new BuiltDeclaration(declaration, node, qualifiedName, content));
        }

        AddSemanticRelationships(built, relationships, relativePath);
    }

    private static IReadOnlyList<RustDeclaration> CollectDeclarations(
        string[] lines,
        string relativePath,
        List<ParserDiagnostic> diagnostics)
    {
        var declarations = new List<RustDeclaration>();
        var attributes = new List<string>();
        for (var index = 0; index < lines.Length; index++)
        {
            var trimmed = StripLineComment(lines[index]).Trim();
            if (trimmed.StartsWith("#[", StringComparison.Ordinal))
            {
                attributes.Add(trimmed);
                continue;
            }

            if (string.IsNullOrWhiteSpace(trimmed))
            {
                continue;
            }

            var statement = DeclarationStatement(lines, index);
            var useMatch = UseRegex().Match(statement);
            var implMatch = ImplRegex().Match(statement);
            var declarationMatch = DeclarationRegex().Match(statement);
            RustDeclaration? declaration = null;
            if (useMatch.Success)
            {
                var path = NormalizeWhitespace(useMatch.Groups["path"].Value);
                declaration = new RustDeclaration(
                    "use",
                    path,
                    CodeNodeKind.Declaration,
                    index + 1,
                    LeadingColumn(lines[index]),
                    FindDeclarationEnd(lines, index),
                    false,
                    statement,
                    attributes.ToArray(),
                    null,
                    null);
            }
            else if (implMatch.Success)
            {
                var traitName = NullIfWhiteSpace(implMatch.Groups["trait"].Value);
                var typeName = implMatch.Groups["type"].Value;
                declaration = new RustDeclaration(
                    "impl",
                    traitName is null ? $"impl {typeName}" : $"impl {traitName} for {typeName}",
                    CodeNodeKind.Declaration,
                    index + 1,
                    LeadingColumn(lines[index]),
                    FindDeclarationEnd(lines, index),
                    statement.Contains('{'),
                    statement,
                    attributes.ToArray(),
                    traitName,
                    typeName);
            }
            else if (declarationMatch.Success)
            {
                var rustKind = declarationMatch.Groups["kind"].Value;
                var nodeKind = NodeKind(rustKind, attributes, declarationMatch.Groups["name"].Value);
                declaration = new RustDeclaration(
                    rustKind,
                    declarationMatch.Groups["name"].Value,
                    nodeKind,
                    index + 1,
                    LeadingColumn(lines[index]),
                    FindDeclarationEnd(lines, index),
                    statement.Contains('{'),
                    statement,
                    attributes.ToArray(),
                    null,
                    null);
            }

            if (declaration is not null)
            {
                declarations.Add(declaration);
                attributes.Clear();
                continue;
            }

            if (attributes.Count > 0 && !trimmed.StartsWith("//", StringComparison.Ordinal))
            {
                attributes.Clear();
            }
        }

        if (declarations.Count == 0 && lines.Any(line => !string.IsNullOrWhiteSpace(line)))
        {
            diagnostics.Add(new ParserDiagnostic(
                "CMRS002",
                $"Rust file '{relativePath}' contained no supported declarations.",
                "info",
                SourceSpan.Unknown(relativePath)));
        }

        return declarations;
    }

    private static void AddSemanticRelationships(
        IReadOnlyList<BuiltDeclaration> declarations,
        List<CodeRelationship> relationships,
        string relativePath)
    {
        var byName = declarations
            .GroupBy(item => item.Declaration.Name, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.ToArray(), StringComparer.Ordinal);
        var callableByName = declarations
            .Where(item => item.Declaration.RustKind == "fn")
            .GroupBy(item => item.Declaration.Name, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.ToArray(), StringComparer.Ordinal);
        var typeByName = declarations
            .Where(item => item.Declaration.RustKind is "struct" or "enum" or "trait")
            .GroupBy(item => item.Declaration.Name, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.ToArray(), StringComparer.Ordinal);

        foreach (var declaration in declarations)
        {
            if (declaration.Declaration.RustKind == "impl")
            {
                AddResolvedRelationship(
                    declaration.Node.Id,
                    declaration.Declaration.TraitName,
                    typeByName,
                    CodeRelationshipKind.Implements,
                    relationships,
                    relativePath);
                AddResolvedRelationship(
                    declaration.Node.Id,
                    declaration.Declaration.TypeName,
                    typeByName,
                    CodeRelationshipKind.References,
                    relationships,
                    relativePath);
            }

            if (declaration.Declaration.RustKind == "use")
            {
                var target = declaration.Declaration.Name
                    .TrimEnd(':', '*')
                    .Split("::", StringSplitOptions.RemoveEmptyEntries)
                    .LastOrDefault();
                AddResolvedRelationship(
                    declaration.Node.Id,
                    target,
                    byName,
                    CodeRelationshipKind.References,
                    relationships,
                    relativePath);
            }

            if (declaration.Declaration.RustKind != "fn")
            {
                continue;
            }

            var body = BodyOnly(declaration.Content);
            foreach (Match match in CallRegex().Matches(body).Cast<Match>().Concat(MethodCallRegex().Matches(body).Cast<Match>()))
            {
                var name = match.Groups["name"].Value;
                if (IgnoredCallNames.Contains(name) ||
                    !callableByName.TryGetValue(name, out var targets) ||
                    targets.Length != 1)
                {
                    continue;
                }

                relationships.Add(Relationship(
                    declaration.Node.Id,
                    targets[0].Node.Id,
                    CodeRelationshipKind.Invokes,
                    name,
                    relativePath));
            }

            foreach (var (name, targets) in typeByName)
            {
                if (targets.Length == 1 && SignatureContainsType(declaration.Declaration.Signature, name))
                {
                    relationships.Add(Relationship(
                        declaration.Node.Id,
                        targets[0].Node.Id,
                        CodeRelationshipKind.UsesType,
                        name,
                        relativePath));
                }
            }
        }
    }

    private static IReadOnlyDictionary<string, string> DeclarationMetadata(
        string relativePath,
        string module,
        RustDeclaration declaration,
        string qualifiedName,
        string parentNodeId)
    {
        var metadata = new Dictionary<string, string>
        {
            ["filePath"] = relativePath,
            ["module"] = module,
            ["qualifiedName"] = qualifiedName,
            ["parentNodeId"] = parentNodeId,
            ["rustKind"] = declaration.RustKind,
            ["signature"] = declaration.Signature,
            ["attributes"] = string.Join(' ', declaration.Attributes)
        };
        if (declaration.TraitName is not null)
        {
            metadata["traitName"] = declaration.TraitName;
        }
        if (declaration.TypeName is not null)
        {
            metadata["typeName"] = declaration.TypeName;
        }
        var exportKind = PythonExportKind(declaration.Attributes);
        if (exportKind is not null)
        {
            metadata["pythonExportKind"] = exportKind;
            metadata["pythonExportName"] = PythonExportName(declaration.Attributes) ?? declaration.Name;
        }
        if (declaration.NodeKind == CodeNodeKind.TestCase)
        {
            metadata["testRole"] = "case";
            metadata["testFramework"] = "rust";
        }
        return metadata;
    }

    private static CodeNodeKind NodeKind(
        string rustKind,
        IReadOnlyList<string> attributes,
        string name)
    {
        return rustKind switch
        {
            "mod" => CodeNodeKind.Namespace,
            "struct" => CodeNodeKind.Struct,
            "enum" => CodeNodeKind.Enum,
            "trait" => CodeNodeKind.Interface,
            "fn" when IsTest(attributes, name) => CodeNodeKind.TestCase,
            "fn" => CodeNodeKind.Method,
            _ => CodeNodeKind.Declaration
        };
    }

    private static string NodeId(
        string module,
        RustDeclaration declaration,
        string qualifiedName)
    {
        var kind = declaration.RustKind;
        return kind == "impl"
            ? $"rust:impl:{module}:{CodeMeshHash.StableId(declaration.Signature)}"
            : $"rust:{kind}:{module}:{qualifiedName}";
    }

    private static CodeRelationship Relationship(
        string sourceNodeId,
        string targetNodeId,
        CodeRelationshipKind kind,
        string? label,
        string relativePath)
    {
        return new CodeRelationship(
            CodeMeshHash.StableId("rust", kind.ToString(), sourceNodeId, targetNodeId, label ?? string.Empty),
            sourceNodeId,
            targetNodeId,
            kind,
            label,
            new Dictionary<string, string> { ["filePath"] = relativePath });
    }

    private static void AddResolvedRelationship(
        string sourceNodeId,
        string? name,
        IReadOnlyDictionary<string, BuiltDeclaration[]> targetsByName,
        CodeRelationshipKind kind,
        List<CodeRelationship> relationships,
        string relativePath)
    {
        if (name is not null &&
            targetsByName.TryGetValue(name.Split("::").Last(), out var targets) &&
            targets.Length == 1)
        {
            relationships.Add(Relationship(
                sourceNodeId,
                targets[0].Node.Id,
                kind,
                name,
                relativePath));
        }
    }

    private static int FindDeclarationEnd(string[] lines, int startIndex)
    {
        var depth = 0;
        var opened = false;
        for (var index = startIndex; index < lines.Length; index++)
        {
            var line = StripLineComment(lines[index]);
            foreach (var character in line)
            {
                if (character == '{')
                {
                    opened = true;
                    depth++;
                }
                else if (character == '}' && opened)
                {
                    depth--;
                }
            }
            if (opened && depth <= 0)
            {
                return index + 1;
            }
            if (!opened && line.Contains(';'))
            {
                return index + 1;
            }
        }
        return Math.Max(1, lines.Length);
    }

    private static string DeclarationStatement(string[] lines, int startIndex)
    {
        var parts = new List<string>();
        for (var index = startIndex; index < Math.Min(lines.Length, startIndex + 12); index++)
        {
            var line = StripLineComment(lines[index]).Trim();
            if (!string.IsNullOrWhiteSpace(line))
            {
                parts.Add(line);
            }
            if (line.Contains('{') || line.Contains(';'))
            {
                break;
            }
        }
        return NormalizeWhitespace(string.Join(' ', parts));
    }

    private static string? PythonExportKind(IReadOnlyList<string> attributes)
    {
        var joined = string.Join(' ', attributes);
        if (joined.Contains("pymodule", StringComparison.Ordinal)) return "module";
        if (joined.Contains("pyclass", StringComparison.Ordinal)) return "class";
        if (joined.Contains("pyfunction", StringComparison.Ordinal)) return "function";
        if (joined.Contains("pymethods", StringComparison.Ordinal)) return "methods";
        return null;
    }

    private static string? PythonExportName(IReadOnlyList<string> attributes)
    {
        var match = PyO3NameRegex().Match(string.Join(' ', attributes));
        return match.Success ? match.Groups["name"].Value : null;
    }

    private static bool IsTest(IReadOnlyList<string> attributes, string name)
    {
        return name.StartsWith("test_", StringComparison.Ordinal) ||
            attributes.Any(attribute =>
                attribute.Contains("#[test]", StringComparison.Ordinal) ||
                attribute.Contains("::test", StringComparison.Ordinal));
    }

    private static bool SignatureContainsType(string signature, string name)
    {
        return Regex.IsMatch(signature, $@"\b{Regex.Escape(name)}\b", RegexOptions.CultureInvariant);
    }

    private static string BodyOnly(string content)
    {
        var opening = content.IndexOf('{');
        return opening >= 0 ? content[(opening + 1)..] : string.Empty;
    }

    private static string StripLineComment(string line)
    {
        var index = line.IndexOf("//", StringComparison.Ordinal);
        return index >= 0 ? line[..index] : line;
    }

    private static string NormalizeWhitespace(string value)
    {
        return Regex.Replace(value, @"\s+", " ").Trim();
    }

    private static string? NullIfWhiteSpace(string value)
    {
        return string.IsNullOrWhiteSpace(value) ? null : value;
    }

    private static int LeadingColumn(string line)
    {
        var index = 0;
        while (index < line.Length && char.IsWhiteSpace(line[index])) index++;
        return index + 1;
    }

    private static string[] NormalizeLines(string text)
    {
        return text.Replace("\r\n", "\n", StringComparison.Ordinal).Replace('\r', '\n').Split('\n');
    }

    private static IEnumerable<string> EnumerateRustFiles(
        string repositoryRoot,
        RepositoryPathFilter? pathFilter)
    {
        return RepositoryPathPolicy.EnumerateFiles(repositoryRoot, "*.rs", pathFilter)
            .OrderBy(file => file, StringComparer.OrdinalIgnoreCase);
    }

    private static bool IsTestFile(string relativePath)
    {
        var segments = relativePath.Split('/', StringSplitOptions.RemoveEmptyEntries);
        return segments.Any(segment => string.Equals(segment, "tests", StringComparison.OrdinalIgnoreCase)) ||
            Path.GetFileNameWithoutExtension(relativePath).EndsWith("_test", StringComparison.OrdinalIgnoreCase);
    }

    private static string ProjectName(string repositoryRoot)
    {
        return new DirectoryInfo(repositoryRoot).Name;
    }

    private static string ModuleName(string relativePath)
    {
        var path = Path.ChangeExtension(relativePath, null).Replace('\\', '/');
        var parts = path.Split('/', StringSplitOptions.RemoveEmptyEntries).ToList();
        if (parts.Count > 0 && string.Equals(parts[0], "src", StringComparison.OrdinalIgnoreCase))
        {
            parts.RemoveAt(0);
        }
        if (parts.Count > 0 && parts[^1] is "lib" or "main" or "mod")
        {
            parts.RemoveAt(parts.Count - 1);
        }
        return parts.Count == 0 ? "crate" : $"crate::{string.Join("::", parts)}";
    }

    private static string NormalizePath(string path)
    {
        return path.Replace('\\', '/');
    }

    private static ParseResult Failure(string message)
    {
        return new ParseResult(
            Capability.WorkerName,
            Capability.Language,
            Array.Empty<CodeNode>(),
            Array.Empty<CodeRelationship>(),
            Array.Empty<CodeContent>(),
            [new ParserDiagnostic("CMRS000", message, "error")],
            DateTimeOffset.UtcNow);
    }

    private static readonly HashSet<string> IgnoredCallNames = new(StringComparer.Ordinal)
    {
        "as", "async", "await", "else", "for", "if", "loop", "match", "move", "return", "while"
    };

    [GeneratedRegex(@"^(?:(?:pub(?:\([^)]*\))?)\s+)?(?:(?:default|unsafe|const|async)\s+)*(?<kind>mod|struct|enum|trait|fn)\s+(?<name>[A-Za-z_][A-Za-z0-9_]*)\b", RegexOptions.CultureInvariant)]
    private static partial Regex DeclarationRegex();

    [GeneratedRegex(@"^(?:(?:pub(?:\([^)]*\))?)\s+)?impl(?:\s*<[^>{}]*>)?\s+(?:(?<trait>[A-Za-z_][A-Za-z0-9_:]*)\s+for\s+)?(?<type>[A-Za-z_][A-Za-z0-9_:]*)\b", RegexOptions.CultureInvariant)]
    private static partial Regex ImplRegex();

    [GeneratedRegex(@"^(?:(?:pub(?:\([^)]*\))?)\s+)?use\s+(?<path>[^;]+);", RegexOptions.CultureInvariant)]
    private static partial Regex UseRegex();

    [GeneratedRegex(@"(?<![.])\b(?:[A-Za-z_][A-Za-z0-9_]*::)*(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*!?\s*\(", RegexOptions.CultureInvariant)]
    private static partial Regex CallRegex();

    [GeneratedRegex(@"\.\s*(?<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(", RegexOptions.CultureInvariant)]
    private static partial Regex MethodCallRegex();

    [GeneratedRegex("\\bname\\s*=\\s*\"(?<name>[A-Za-z_][A-Za-z0-9_]*)\"", RegexOptions.CultureInvariant)]
    private static partial Regex PyO3NameRegex();

    private sealed record RustDeclaration(
        string RustKind,
        string Name,
        CodeNodeKind NodeKind,
        int StartLine,
        int StartColumn,
        int EndLine,
        bool HasBody,
        string Signature,
        IReadOnlyList<string> Attributes,
        string? TraitName,
        string? TypeName);

    private sealed record BuiltDeclaration(
        RustDeclaration Declaration,
        CodeNode Node,
        string QualifiedName,
        string Content);
}
