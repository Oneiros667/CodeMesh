using CodeMesh.Domain.Graph;

namespace CodeMesh.Domain.Contracts;

public sealed record AgentContextQuery(
    string Query,
    string? RepositoryId,
    int Limit = 8,
    IReadOnlyList<string>? Kinds = null,
    IReadOnlyDictionary<string, string>? Filters = null);

public sealed record CodeSearchHit(
    string NodeId,
    string StableKey,
    CodeNodeKind Kind,
    string FilePath,
    int StartLine,
    int EndLine,
    double Score,
    string? Preview);

public sealed record AgentContextResult(
    AgentContextQuery Query,
    IReadOnlyList<CodeSearchHit> Hits,
    DateTimeOffset GeneratedAt);
