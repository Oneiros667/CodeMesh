using CodeMesh.Domain.Graph;

namespace CodeMesh.Domain.Contracts;

public sealed record ParseRequest(
    string RepositoryRoot,
    string? SolutionPath,
    string? ProjectPath,
    string Language,
    IReadOnlyDictionary<string, string> Options);

public sealed record ParserCapability(
    string WorkerName,
    string Language,
    string Version,
    IReadOnlyList<string> SupportedFileExtensions,
    IReadOnlyList<string> SupportedInputs);

public sealed record ParserDiagnostic(
    string Code,
    string Message,
    string Severity,
    SourceSpan? Span = null);

public sealed record ParseResult(
    string ParserName,
    string Language,
    IReadOnlyList<CodeNode> Nodes,
    IReadOnlyList<CodeRelationship> Relationships,
    IReadOnlyList<CodeContent> Contents,
    IReadOnlyList<ParserDiagnostic> Diagnostics,
    DateTimeOffset ParsedAt);

public interface IParserClient
{
    Task<ParserCapability> GetCapabilityAsync(CancellationToken cancellationToken = default);

    Task<ParseResult> ParseAsync(ParseRequest request, CancellationToken cancellationToken = default);
}
