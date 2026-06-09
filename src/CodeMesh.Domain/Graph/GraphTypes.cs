namespace CodeMesh.Domain.Graph;

public enum CodeNodeKind
{
    Repository,
    Solution,
    Project,
    Assembly,
    Namespace,
    File,
    Declaration,
    Class,
    Interface,
    Struct,
    Enum,
    Delegate,
    Method,
    Constructor,
    Property,
    Field,
    Event,
    Parameter,
    Lambda,
    Unknown
}

public enum CodeRelationshipKind
{
    Contains,
    Defines,
    Invokes,
    References,
    UsesType,
    Inherits,
    Implements,
    Returns,
    HasParameter,
    Reads,
    Writes,
    Overrides,
    Unknown
}

public sealed record RepositoryRef(
    string Id,
    string RootPath,
    string? RemoteUrl = null,
    string? Branch = null,
    string? Commit = null);

public sealed record SourceSpan(
    string FilePath,
    int StartLine,
    int StartColumn,
    int EndLine,
    int EndColumn)
{
    public static SourceSpan Unknown(string filePath = "") => new(filePath, 0, 0, 0, 0);
}

public sealed record CodeNode(
    string Id,
    string StableKey,
    CodeNodeKind Kind,
    string Name,
    string Language,
    string Project,
    SourceSpan Span,
    string ContentHash,
    IReadOnlyDictionary<string, string> Metadata);

public sealed record CodeRelationship(
    string Id,
    string SourceNodeId,
    string TargetNodeId,
    CodeRelationshipKind Kind,
    string? Label,
    IReadOnlyDictionary<string, string> Metadata);

public sealed record CodeContent(
    string Hash,
    string Text,
    string MediaType,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt);

public sealed record EmbeddingRecord(
    string Id,
    string NodeId,
    string ContentHash,
    string Provider,
    string Model,
    int Dimensions,
    IReadOnlyList<float> Vector,
    IReadOnlyDictionary<string, string> Metadata);

public sealed record CodeNodeSummary(
    string Id,
    string RepositoryId,
    string RepositoryRoot,
    string IngestionRunId,
    string NodeId,
    string StableKey,
    CodeNodeKind Kind,
    string Name,
    string Language,
    string Project,
    SourceSpan Span,
    string ContentHash,
    string SummaryKind,
    string Summary,
    IReadOnlyList<string> Tags,
    string Confidence,
    string Provider,
    string Model,
    string PromptVersion,
    string PromptHash,
    DateTimeOffset GeneratedAt,
    string Status,
    string? Error,
    IReadOnlyDictionary<string, string> Metadata);

public sealed record CodeGraphBatch(
    string BatchId,
    RepositoryRef Repository,
    IReadOnlyList<CodeNode> Nodes,
    IReadOnlyList<CodeRelationship> Relationships,
    IReadOnlyList<CodeContent> Contents,
    DateTimeOffset CreatedAt);

public sealed record VectorSearchMatch(
    string NodeId,
    string ContentHash,
    double Score,
    string? Preview,
    IReadOnlyDictionary<string, string> Metadata);
