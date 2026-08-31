using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Ingestion;

public sealed class CompositeParserClient : IParserClient
{
    private readonly IReadOnlyDictionary<string, IParserClient> _clients;
    private readonly IReadOnlyList<string> _languages;

    public CompositeParserClient(IReadOnlyDictionary<string, IParserClient> clients)
    {
        ArgumentNullException.ThrowIfNull(clients);
        _clients = clients.ToDictionary(
            item => NormalizeLanguage(item.Key),
            item => item.Value,
            StringComparer.Ordinal);
        _languages = _clients.Keys.OrderBy(value => value, StringComparer.Ordinal).ToArray();
        if (_languages.Count < 2)
        {
            throw new ArgumentException(
                "Composite parsing requires at least two distinct languages.",
                nameof(clients));
        }
    }

    public async Task<ParserCapability> GetCapabilityAsync(
        CancellationToken cancellationToken = default)
    {
        var capabilities = await Task.WhenAll(_languages.Select(language =>
            _clients[language].GetCapabilityAsync(cancellationToken))).ConfigureAwait(false);
        return new ParserCapability(
            "codemesh-parser-composite",
            string.Join(',', _languages),
            "1.0.0",
            capabilities
                .SelectMany(capability => capability.SupportedFileExtensions)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(value => value, StringComparer.OrdinalIgnoreCase)
                .ToArray(),
            capabilities
                .SelectMany(capability => capability.SupportedInputs)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(value => value, StringComparer.OrdinalIgnoreCase)
                .ToArray());
    }

    public async Task<ParseResult> ParseAsync(
        ParseRequest request,
        CancellationToken cancellationToken = default)
    {
        var requestedLanguages = ParseLanguages(request.Language);
        if (!_languages.SequenceEqual(requestedLanguages, StringComparer.Ordinal))
        {
            throw new InvalidOperationException(
                $"Composite parser is configured for '{string.Join(',', _languages)}' " +
                $"but the request selected '{string.Join(',', requestedLanguages)}'.");
        }

        var results = await Task.WhenAll(requestedLanguages.Select(language =>
            _clients[language].ParseAsync(
                request with { Language = language },
                cancellationToken))).ConfigureAwait(false);

        var nodes = results.SelectMany(result => result.Nodes).ToArray();
        var relationships = results.SelectMany(result => result.Relationships).ToList();
        AddPyO3Relationships(nodes, relationships);
        relationships = CoalesceRelationships(relationships);

        EnsureUnique(
            nodes,
            node => node.Id,
            "node");
        EnsureUnique(
            relationships,
            relationship => relationship.Id,
            "relationship");

        return new ParseResult(
            $"codemesh-parser-composite-v1[{string.Join(';', results.Select(result => $"{result.Language}={result.ParserName}"))}]",
            string.Join(',', requestedLanguages),
            nodes,
            relationships,
            results
                .SelectMany(result => result.Contents)
                .GroupBy(content => content.Hash, StringComparer.Ordinal)
                .Select(group => group.First())
                .ToArray(),
            results.SelectMany(result => result.Diagnostics).ToArray(),
            results.Max(result => result.ParsedAt));
    }

    public static IReadOnlyList<string> ParseLanguages(string languageSet)
    {
        var languages = languageSet
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(NormalizeLanguage)
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Distinct(StringComparer.Ordinal)
            .OrderBy(value => value, StringComparer.Ordinal)
            .ToArray();
        if (languages.Length == 0)
        {
            throw new InvalidOperationException("At least one ingestion language is required.");
        }

        return languages;
    }

    public static string NormalizeLanguage(string language)
    {
        return language.Trim().ToLowerInvariant() switch
        {
            "cs" or "c#" => "csharp",
            "deploy" or "docker" or "compose" => "deployment",
            "md" => "markdown",
            "py" => "python",
            "rs" => "rust",
            var value => value
        };
    }

    private static void EnsureUnique<T>(
        IEnumerable<T> values,
        Func<T, string> identity,
        string kind)
    {
        var duplicate = values
            .GroupBy(identity, StringComparer.Ordinal)
            .FirstOrDefault(group => group.Count() > 1);
        if (duplicate is not null)
        {
            throw new InvalidOperationException(
                $"Composite parser results contain duplicate {kind} id '{duplicate.Key}'.");
        }
    }

    private static List<CodeRelationship> CoalesceRelationships(
        IEnumerable<CodeRelationship> relationships)
    {
        var coalesced = new List<CodeRelationship>();
        foreach (var group in relationships.GroupBy(
                     relationship => relationship.Id,
                     StringComparer.Ordinal))
        {
            var first = group.First();
            if (group.Any(relationship =>
                    !string.Equals(
                        relationship.SourceNodeId,
                        first.SourceNodeId,
                        StringComparison.Ordinal) ||
                    !string.Equals(
                        relationship.TargetNodeId,
                        first.TargetNodeId,
                        StringComparison.Ordinal) ||
                    relationship.Kind != first.Kind ||
                    !string.Equals(
                        relationship.Label,
                        first.Label,
                        StringComparison.Ordinal)))
            {
                throw new InvalidOperationException(
                    $"Composite parser relationship id collision '{group.Key}'.");
            }
            coalesced.Add(first);
        }
        return coalesced;
    }

    private static void AddPyO3Relationships(
        IReadOnlyList<CodeNode> nodes,
        List<CodeRelationship> relationships)
    {
        var rustExports = nodes
            .Where(node =>
                string.Equals(node.Language, "rust", StringComparison.Ordinal) &&
                node.Metadata.ContainsKey("pythonExportName"))
            .ToArray();
        if (rustExports.Length == 0)
        {
            return;
        }

        var exportsByName = rustExports
            .GroupBy(node => node.Metadata["pythonExportName"], StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.ToArray(), StringComparer.Ordinal);
        var pythonImports = nodes
            .Where(node =>
                string.Equals(node.Language, "python", StringComparison.Ordinal) &&
                node.Metadata.TryGetValue("pythonKind", out var kind) &&
                string.Equals(kind, "import", StringComparison.Ordinal))
            .ToDictionary(node => node.Id, StringComparer.Ordinal);

        foreach (var import in pythonImports.Values)
        {
            import.Metadata.TryGetValue("importModule", out var module);
            import.Metadata.TryGetValue("importedName", out var importedName);
            var moduleName = module?.Split('.').LastOrDefault();
            var targetName = string.IsNullOrWhiteSpace(importedName) ? moduleName : importedName;
            AddCrossLanguageRelationship(
                import.Id,
                targetName,
                exportsByName,
                CodeRelationshipKind.References,
                targetName,
                relationships);
        }

        foreach (var invocation in relationships
            .Where(relationship =>
                relationship.Kind == CodeRelationshipKind.Invokes &&
                pythonImports.ContainsKey(relationship.TargetNodeId))
            .ToArray())
        {
            AddCrossLanguageRelationship(
                invocation.SourceNodeId,
                invocation.Label,
                exportsByName,
                CodeRelationshipKind.Invokes,
                invocation.Label,
                relationships);
        }
    }

    private static void AddCrossLanguageRelationship(
        string sourceNodeId,
        string? exportName,
        IReadOnlyDictionary<string, CodeNode[]> exportsByName,
        CodeRelationshipKind kind,
        string? label,
        List<CodeRelationship> relationships)
    {
        if (string.IsNullOrWhiteSpace(exportName) ||
            !exportsByName.TryGetValue(exportName, out var targets) ||
            targets.Length != 1)
        {
            return;
        }

        var target = targets[0];
        var id = CodeMeshHash.StableId(
            "cross-language",
            "pyo3",
            kind.ToString(),
            sourceNodeId,
            target.Id,
            label ?? string.Empty);
        if (relationships.Any(relationship => string.Equals(relationship.Id, id, StringComparison.Ordinal)))
        {
            return;
        }
        relationships.Add(new CodeRelationship(
            id,
            sourceNodeId,
            target.Id,
            kind,
            label,
            new Dictionary<string, string>
            {
                ["boundary"] = "pyo3",
                ["sourceLanguage"] = "python",
                ["targetLanguage"] = "rust"
            }));
    }
}
