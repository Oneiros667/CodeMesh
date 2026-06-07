using System.Text.Json;
using System.Text.Json.Serialization;
using CodeMesh.Domain.Graph;

namespace CodeMesh.Domain.Contracts;

public sealed record AgentContextQuery(
    [property: JsonPropertyName("query")] string Query,
    [property: JsonPropertyName("repository_id")] string? RepositoryId = null,
    [property: JsonPropertyName("limit")] int Limit = 8,
    [property: JsonPropertyName("kinds")] IReadOnlyList<string>? Kinds = null,
    [property: JsonPropertyName("filters")] IReadOnlyDictionary<string, string>? Filters = null,
    [property: JsonPropertyName("vector")] IReadOnlyList<float>? Vector = null,
    [property: JsonPropertyName("expand_context")] bool ExpandContext = true,
    [property: JsonPropertyName("context_depth")] int ContextDepth = 4,
    [property: JsonPropertyName("include_context_relationships")] bool IncludeContextRelationships = false,
    [property: JsonPropertyName("context_relationship_limit")] int ContextRelationshipLimit = 8);

public sealed record CodeSearchHit(
    [property: JsonPropertyName("node_id")] string NodeId,
    [property: JsonPropertyName("stable_key")] string StableKey,
    [property: JsonPropertyName("kind")]
    [property: JsonConverter(typeof(JsonStringEnumConverter<CodeNodeKind>))]
    CodeNodeKind Kind,
    [property: JsonPropertyName("file_path")] string FilePath,
    [property: JsonPropertyName("start_line")] int StartLine,
    [property: JsonPropertyName("end_line")] int EndLine,
    [property: JsonPropertyName("score")] double Score,
    [property: JsonPropertyName("repository_id")] string? RepositoryId = null,
    [property: JsonPropertyName("content_hash")] string? ContentHash = null,
    [property: JsonPropertyName("score_components")] IReadOnlyDictionary<string, double>? ScoreComponents = null,
    [property: JsonPropertyName("expanded_context")] IReadOnlyDictionary<string, JsonElement>? ExpandedContext = null,
    [property: JsonPropertyName("preview")] string? Preview = null);

public sealed record AgentContextDiagnostics(
    [property: JsonPropertyName("mode")] string Mode,
    [property: JsonPropertyName("embedding_attempted")] bool EmbeddingAttempted,
    [property: JsonPropertyName("embedding_source")] string EmbeddingSource,
    [property: JsonPropertyName("model_provider")] string ModelProvider,
    [property: JsonPropertyName("vector_available")] bool VectorAvailable,
    [property: JsonPropertyName("vector_hit_count")] int VectorHitCount,
    [property: JsonPropertyName("lexical_hit_count")] int LexicalHitCount,
    [property: JsonPropertyName("lexical_fallback")] bool LexicalFallback,
    [property: JsonPropertyName("hit_count")] int HitCount);

public sealed record AgentContextResult(
    [property: JsonPropertyName("query")] AgentContextQuery Query,
    [property: JsonPropertyName("hits")] IReadOnlyList<CodeSearchHit> Hits,
    [property: JsonPropertyName("diagnostics")] AgentContextDiagnostics? Diagnostics,
    [property: JsonPropertyName("generated_at")] DateTimeOffset GeneratedAt);

public sealed record AgentContextPackageQuery(
    [property: JsonPropertyName("query")] string Query,
    [property: JsonPropertyName("repository_id")] string? RepositoryId = null,
    [property: JsonPropertyName("limit")] int Limit = 8,
    [property: JsonPropertyName("max_characters")] int MaxCharacters = 12000,
    [property: JsonPropertyName("kinds")] IReadOnlyList<string>? Kinds = null,
    [property: JsonPropertyName("filters")] IReadOnlyDictionary<string, string>? Filters = null,
    [property: JsonPropertyName("vector")] IReadOnlyList<float>? Vector = null,
    [property: JsonPropertyName("context_depth")] int ContextDepth = 4,
    [property: JsonPropertyName("include_content")] bool IncludeContent = true,
    [property: JsonPropertyName("include_relationships")] bool IncludeRelationships = true,
    [property: JsonPropertyName("relationship_limit")] int RelationshipLimit = 8,
    [property: JsonPropertyName("caller_limit")] int? CallerLimit = null,
    [property: JsonPropertyName("callee_limit")] int? CalleeLimit = null,
    [property: JsonPropertyName("read_limit")] int? ReadLimit = null,
    [property: JsonPropertyName("write_limit")] int? WriteLimit = null,
    [property: JsonPropertyName("contains_limit")] int? ContainsLimit = null,
    [property: JsonPropertyName("definition_limit")] int? DefinitionLimit = null,
    [property: JsonPropertyName("uses_type_limit")] int? UsesTypeLimit = null,
    [property: JsonPropertyName("include_repository")] bool IncludeRepository = true);

public sealed record AgentContextPackageItem(
    [property: JsonPropertyName("hit")] CodeSearchHit Hit,
    [property: JsonPropertyName("node")] IReadOnlyDictionary<string, JsonElement>? Node = null,
    [property: JsonPropertyName("content")] IReadOnlyDictionary<string, JsonElement>? Content = null,
    [property: JsonPropertyName("snippet")] string? Snippet = null,
    [property: JsonPropertyName("relationships")] IReadOnlyList<IReadOnlyDictionary<string, JsonElement>>? Relationships = null,
    [property: JsonPropertyName("relationship_groups")] IReadOnlyDictionary<string, IReadOnlyList<IReadOnlyDictionary<string, JsonElement>>>? RelationshipGroups = null,
    [property: JsonPropertyName("rationale")] IReadOnlyDictionary<string, JsonElement>? Rationale = null);

public sealed record AgentContextPackageResult(
    [property: JsonPropertyName("query")] AgentContextPackageQuery Query,
    [property: JsonPropertyName("repository")] IReadOnlyDictionary<string, JsonElement>? Repository,
    [property: JsonPropertyName("latest_run")] IReadOnlyDictionary<string, JsonElement>? LatestRun,
    [property: JsonPropertyName("items")] IReadOnlyList<AgentContextPackageItem> Items,
    [property: JsonPropertyName("total_snippet_characters")] int TotalSnippetCharacters,
    [property: JsonPropertyName("generated_at")] DateTimeOffset GeneratedAt);

public sealed record AgentSymbolQuery(
    [property: JsonPropertyName("query")] string Query,
    [property: JsonPropertyName("repository_id")] string? RepositoryId = null,
    [property: JsonPropertyName("limit")] int Limit = 20,
    [property: JsonPropertyName("kinds")] IReadOnlyList<string>? Kinds = null,
    [property: JsonPropertyName("filters")] IReadOnlyDictionary<string, string>? Filters = null,
    [property: JsonPropertyName("include_declarations")] bool IncludeDeclarations = true);

public sealed record AgentSymbolSearchHit(
    [property: JsonPropertyName("node")] IReadOnlyDictionary<string, JsonElement> Node,
    [property: JsonPropertyName("declaration")] IReadOnlyDictionary<string, JsonElement>? Declaration,
    [property: JsonPropertyName("score")] double Score,
    [property: JsonPropertyName("score_components")] IReadOnlyDictionary<string, double>? ScoreComponents = null);

public sealed record AgentSymbolSearchResult(
    [property: JsonPropertyName("query")] AgentSymbolQuery Query,
    [property: JsonPropertyName("symbols")] IReadOnlyList<AgentSymbolSearchHit> Symbols,
    [property: JsonPropertyName("generated_at")] DateTimeOffset GeneratedAt);

public sealed record AgentNodeLookup(
    [property: JsonPropertyName("node_id")] string NodeId,
    [property: JsonPropertyName("repository_id")] string? RepositoryId = null,
    [property: JsonPropertyName("include_content")] bool IncludeContent = true,
    [property: JsonPropertyName("include_neighbors")] bool IncludeNeighbors = true);

public sealed record AgentNodeResult(
    [property: JsonPropertyName("node")] IReadOnlyDictionary<string, JsonElement>? Node,
    [property: JsonPropertyName("content")] IReadOnlyDictionary<string, JsonElement>? Content,
    [property: JsonPropertyName("relationships")] IReadOnlyList<IReadOnlyDictionary<string, JsonElement>> Relationships);

public sealed record AgentNeighborQuery(
    [property: JsonPropertyName("node_id")] string NodeId,
    [property: JsonPropertyName("repository_id")] string? RepositoryId = null,
    [property: JsonPropertyName("depth")] int Depth = 1,
    [property: JsonPropertyName("relationship_kinds")] IReadOnlyList<string>? RelationshipKinds = null);

public sealed record AgentNeighborResult(
    [property: JsonPropertyName("relationships")] IReadOnlyList<IReadOnlyDictionary<string, JsonElement>> Relationships);
