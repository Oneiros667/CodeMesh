using System.Text.Json;
using System.Text.Json.Serialization;
using CodeMesh.Domain.Graph;

namespace CodeMesh.Domain.Contracts;

public sealed record AgentHealthResult(
    [property: JsonPropertyName("service")] string Service,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("checked_at")] DateTimeOffset CheckedAt,
    [property: JsonPropertyName("components")] IReadOnlyDictionary<string, JsonElement> Components);

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
    [property: JsonPropertyName("summary_hit_count")] int SummaryHitCount,
    [property: JsonPropertyName("vector_candidate_count")] int VectorCandidateCount,
    [property: JsonPropertyName("lexical_candidate_count")] int LexicalCandidateCount,
    [property: JsonPropertyName("summary_candidate_count")] int SummaryCandidateCount,
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
    [property: JsonPropertyName("summary")] IReadOnlyDictionary<string, JsonElement>? Summary = null,
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
    [property: JsonPropertyName("node")] IReadOnlyDictionary<string, JsonElement>? Node,
    [property: JsonPropertyName("content")] IReadOnlyDictionary<string, JsonElement>? Content,
    [property: JsonPropertyName("relationships")] IReadOnlyList<IReadOnlyDictionary<string, JsonElement>> Relationships);

public sealed record AgentRepositorySummary(
    [property: JsonPropertyName("repository_id")] string RepositoryId,
    [property: JsonPropertyName("alias")] string? Alias,
    [property: JsonPropertyName("root_path")] string RootPath,
    [property: JsonPropertyName("remote_url")] string? RemoteUrl,
    [property: JsonPropertyName("branch")] string? Branch,
    [property: JsonPropertyName("commit")] string? Commit,
    [property: JsonPropertyName("first_seen_at")] DateTimeOffset? FirstSeenAt,
    [property: JsonPropertyName("last_seen_at")] DateTimeOffset? LastSeenAt,
    [property: JsonPropertyName("last_run_id")] string? LastRunId,
    [property: JsonPropertyName("last_stage")] string? LastStage,
    [property: JsonPropertyName("last_message")] string? LastMessage,
    [property: JsonPropertyName("node_count")] int NodeCount,
    [property: JsonPropertyName("relationship_count")] int RelationshipCount,
    [property: JsonPropertyName("content_count")] int ContentCount,
    [property: JsonPropertyName("embedding_count")] int? EmbeddingCount,
    [property: JsonPropertyName("metadata")] IReadOnlyDictionary<string, string>? Metadata);

public sealed record AgentRepositoryListResult(
    [property: JsonPropertyName("repositories")] IReadOnlyList<AgentRepositorySummary> Repositories);

public sealed record AgentNodeSummaryCoverageResult(
    [property: JsonPropertyName("repository_id")] string RepositoryId,
    [property: JsonPropertyName("total_count")] int TotalCount,
    [property: JsonPropertyName("completed_count")] int CompletedCount,
    [property: JsonPropertyName("failed_count")] int FailedCount,
    [property: JsonPropertyName("status_counts")] IReadOnlyDictionary<string, int> StatusCounts,
    [property: JsonPropertyName("kind_counts")] IReadOnlyDictionary<string, int> KindCounts,
    [property: JsonPropertyName("provider_model_counts")] IReadOnlyDictionary<string, int> ProviderModelCounts,
    [property: JsonPropertyName("recent_failures")] IReadOnlyList<IReadOnlyDictionary<string, JsonElement>> RecentFailures,
    [property: JsonPropertyName("generated_at")] DateTimeOffset GeneratedAt);

public sealed record AgentIngestionRunSummary(
    [property: JsonPropertyName("run_id")] string RunId,
    [property: JsonPropertyName("repository_id")] string RepositoryId,
    [property: JsonPropertyName("repository_root")] string RepositoryRoot,
    [property: JsonPropertyName("stage")] string Stage,
    [property: JsonPropertyName("started_at")] DateTimeOffset? StartedAt,
    [property: JsonPropertyName("finished_at")] DateTimeOffset? FinishedAt,
    [property: JsonPropertyName("message")] string? Message,
    [property: JsonPropertyName("language")] string Language,
    [property: JsonPropertyName("parser_name")] string ParserName,
    [property: JsonPropertyName("solution_path")] string? SolutionPath,
    [property: JsonPropertyName("project_path")] string? ProjectPath,
    [property: JsonPropertyName("dry_run")] bool DryRun,
    [property: JsonPropertyName("skip_embeddings")] bool SkipEmbeddings,
    [property: JsonPropertyName("embedding_provider")] string EmbeddingProvider,
    [property: JsonPropertyName("embedding_model")] string EmbeddingModel,
    [property: JsonPropertyName("node_count")] int NodeCount,
    [property: JsonPropertyName("relationship_count")] int RelationshipCount,
    [property: JsonPropertyName("content_count")] int ContentCount,
    [property: JsonPropertyName("embedding_count")] int EmbeddingCount,
    [property: JsonPropertyName("stats")] IReadOnlyDictionary<string, JsonElement>? Stats,
    [property: JsonPropertyName("diagnostic_count")] int DiagnosticCount,
    [property: JsonPropertyName("error_diagnostic_count")] int ErrorDiagnosticCount,
    [property: JsonPropertyName("warning_diagnostic_count")] int WarningDiagnosticCount,
    [property: JsonPropertyName("metadata")] IReadOnlyDictionary<string, string>? Metadata);

public sealed record AgentIngestionRunListResult(
    [property: JsonPropertyName("runs")] IReadOnlyList<AgentIngestionRunSummary> Runs);
