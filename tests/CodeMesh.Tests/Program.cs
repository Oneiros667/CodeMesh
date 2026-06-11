using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using CodeMesh.Control.Configuration;
using CodeMesh.Control.AgentAccess;
using CodeMesh.Control.Diagnostics;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Health;
using CodeMesh.Domain.Utilities;
using CodeMesh.Ingestion;
using CodeMesh.Ingestion.Embedding;
using CodeMesh.Ingestion.Summary;
using CodeMesh.Parser.CSharp;
using CodeMesh.Storage.Memory;
using CodeMesh.Storage.Mongo;
using CodeMesh.Storage.Neo4j;
using CodeMesh.Storage.Qdrant;

var tests = new (string Name, Func<Task> Run)[]
{
    ("sha256 helper is deterministic", TestHash),
    ("environment file loader fills missing variables", TestEnvironmentFileLoaderFillsMissingVariables),
    ("agent access contracts map REST JSON", TestAgentAccessContractsMapRestJson),
    ("agent access client calls REST endpoints", TestAgentAccessClientCallsRestEndpoints),
    ("ingestion writes parser output", TestIngestionWritesParserOutput),
    ("dry-run ingestion skips stores", TestDryRunSkipsStores),
    ("repository refresh removes stale records", TestRepositoryRefreshRemovesStaleRecords),
    ("incremental ingestion skips unchanged records", TestIncrementalIngestionSkipsUnchangedRecords),
    ("incremental ingestion skips unchanged summaries", TestIncrementalIngestionSkipsUnchangedSummaries),
    ("forced embedding ingestion rebuilds unchanged embeddings", TestForcedEmbeddingIngestionRebuildsUnchangedEmbeddings),
    ("embedding verifier reports missing and stale vectors", TestEmbeddingVerifierReportsMissingAndStaleVectors),
    ("repository cleanup removes indexed data", TestRepositoryCleanupRemovesIndexedData),
    ("repository aliases are generated and resolved", TestRepositoryAliasesAreGeneratedAndResolved),
    ("ingestion writes repository registry records", TestIngestionWritesRepositoryRegistryRecords),
    ("status uses configured ollama endpoint", TestStatusUsesConfiguredOllamaEndpoint),
    ("status retries transient ollama failures", TestStatusRetriesTransientOllamaFailures),
    ("status degrades when configured model is missing", TestStatusDegradesWhenConfiguredModelIsMissing),
    ("ollama embedding provider maps responses", TestOllamaEmbeddingProviderMapsResponses),
    ("lm studio embedding provider maps responses", TestLmStudioEmbeddingProviderMapsResponses),
    ("lm studio summary provider accepts numeric confidence", TestLmStudioSummaryProviderAcceptsNumericConfidence),
    ("mongodb content store round-trips content", TestMongoContentStoreRoundTripsContent),
    ("mongodb registry store round-trips repositories and runs", TestMongoRegistryStoreRoundTripsRepositoriesAndRuns),
    ("neo4j graph store round-trips graph", TestNeo4jGraphStoreRoundTripsGraph),
    ("qdrant vector store round-trips embeddings", TestQdrantVectorStoreRoundTripsEmbeddings),
    ("csharp parser emits Roslyn symbols", TestCSharpParserEmitsRoslynSymbols),
    ("csharp parser emits invocation and member access relationships", TestCSharpParserEmitsInvocationAndMemberAccessRelationships),
    ("csharp parser separates partial declarations from symbols", TestCSharpParserSeparatesPartialDeclarations),
    ("csharp parser honors project compile items", TestCSharpParserHonorsProjectCompileItems),
    ("csharp parser parses YoutubeDownloader sample", TestYoutubeDownloaderSampleParser)
};

var failures = 0;
var skipped = 0;

foreach (var test in tests)
{
    try
    {
        await test.Run().ConfigureAwait(false);
        Console.WriteLine($"[pass] {test.Name}");
    }
    catch (SkipTestException exception)
    {
        skipped++;
        Console.WriteLine($"[skip] {test.Name}: {exception.Message}");
    }
    catch (Exception exception)
    {
        failures++;
        Console.Error.WriteLine($"[fail] {test.Name}: {exception.Message}");
    }
}

if (failures > 0)
{
    Console.Error.WriteLine($"{failures} test(s) failed.");
    return 1;
}

Console.WriteLine($"{tests.Length - skipped} test(s) passed, {skipped} skipped.");
return 0;

static Task TestHash()
{
    Equal(
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
        CodeMeshHash.Sha256Hex("abc"),
        "SHA-256 output changed.");

    return Task.CompletedTask;
}

static Task TestEnvironmentFileLoaderFillsMissingVariables()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-env-loader-test-{Guid.NewGuid():N}");
    var missingKey = $"CODEMESH_TEST_ENV_MISSING_{Guid.NewGuid():N}";
    var quotedKey = $"CODEMESH_TEST_ENV_QUOTED_{Guid.NewGuid():N}";
    var existingKey = $"CODEMESH_TEST_ENV_EXISTING_{Guid.NewGuid():N}";

    try
    {
        Directory.CreateDirectory(root);
        File.WriteAllLines(
            Path.Combine(root, ".env"),
            [
                "# comment",
                $"{missingKey}=from-env-file",
                $"{quotedKey}=\"quoted value\"",
                $"{existingKey}=from-env-file"
            ]);

        Environment.SetEnvironmentVariable(missingKey, null);
        Environment.SetEnvironmentVariable(quotedKey, null);
        Environment.SetEnvironmentVariable(existingKey, "already-set");

        var loaded = EnvironmentFileLoader.LoadIfExists(root);

        Equal(2, loaded, "Environment loader loaded an unexpected number of variables.");
        Equal("from-env-file", Environment.GetEnvironmentVariable(missingKey) ?? string.Empty, "Environment loader did not set a missing variable.");
        Equal("quoted value", Environment.GetEnvironmentVariable(quotedKey) ?? string.Empty, "Environment loader did not unquote a value.");
        Equal("already-set", Environment.GetEnvironmentVariable(existingKey) ?? string.Empty, "Environment loader overwrote an existing variable.");
    }
    finally
    {
        Environment.SetEnvironmentVariable(missingKey, null);
        Environment.SetEnvironmentVariable(quotedKey, null);
        Environment.SetEnvironmentVariable(existingKey, null);

        if (Directory.Exists(root))
        {
            Directory.Delete(root, recursive: true);
        }
    }

    return Task.CompletedTask;
}

static Task TestAgentAccessContractsMapRestJson()
{
    var options = new JsonSerializerOptions(JsonSerializerDefaults.Web);
    var serializedQuery = JsonSerializer.Serialize(
        new AgentContextQuery(
            "DownloadAsync",
            RepositoryId: "repo:test",
            Kinds: ["Method"],
            Filters: new Dictionary<string, string> { ["project"] = "Sample" },
            Vector: [0.1f, 0.2f],
            ExpandContext: false,
            ContextRelationshipLimit: 4),
        options);

    if (!serializedQuery.Contains("\"repository_id\":\"repo:test\"", StringComparison.Ordinal) ||
        !serializedQuery.Contains("\"context_relationship_limit\":4", StringComparison.Ordinal))
    {
        throw new InvalidOperationException("Agent context query did not serialize using Agent Access snake_case fields.");
    }

    var serializedPackageQuery = JsonSerializer.Serialize(
        new AgentContextPackageQuery(
            "DownloadAsync",
            RepositoryId: "repo:test",
            MaxCharacters: 4000,
            CallerLimit: 2,
            UsesTypeLimit: 0),
        options);

    if (!serializedPackageQuery.Contains("\"max_characters\":4000", StringComparison.Ordinal) ||
        !serializedPackageQuery.Contains("\"uses_type_limit\":0", StringComparison.Ordinal))
    {
        throw new InvalidOperationException("Agent context package query did not serialize using Agent Access snake_case fields.");
    }

    var context = JsonSerializer.Deserialize<AgentContextResult>(
        """
        {
          "query": {
            "query": "DownloadAsync",
            "repository_id": "repo:test",
            "limit": 5,
            "kinds": ["Method"],
            "filters": {"project": "Sample"},
            "vector": [0.1, 0.2],
            "expand_context": false,
            "context_depth": 2,
            "include_context_relationships": true,
            "context_relationship_limit": 4
          },
          "hits": [
            {
              "node_id": "node:download",
              "stable_key": "stable:download",
              "kind": "Method",
              "file_path": "Downloader.cs",
              "start_line": 10,
              "end_line": 20,
              "score": 0.91,
              "repository_id": "repo:test",
              "content_hash": "content:download",
              "score_components": {"vector_score": 0.6},
              "expanded_context": {"reason": "defined_ancestor"},
              "preview": "Task DownloadAsync"
            }
          ],
          "diagnostics": {
            "mode": "hybrid",
            "embedding_attempted": true,
            "embedding_source": "model_provider",
            "model_provider": "lmstudio",
            "vector_available": true,
            "vector_hit_count": 7,
            "lexical_hit_count": 3,
            "summary_hit_count": 2,
            "vector_candidate_count": 9,
            "lexical_candidate_count": 5,
            "summary_candidate_count": 4,
            "lexical_fallback": false,
            "hit_count": 1
          },
          "generated_at": "2026-06-06T10:00:00Z"
        }
        """,
        options);

    NotNull(context, "Agent context result did not deserialize.");
    Equal("repo:test", context!.Query.RepositoryId ?? string.Empty, "Agent context query repository id did not map from snake_case.");
    Equal(false, context.Query.ExpandContext, "Agent context query expansion flag changed.");
    Equal(4, context.Query.ContextRelationshipLimit, "Agent context relationship limit did not deserialize.");
    Equal(CodeNodeKind.Method, context.Hits[0].Kind, "Agent context hit kind did not deserialize.");
    Equal("content:download", context.Hits[0].ContentHash ?? string.Empty, "Agent context hit content hash did not deserialize.");
    Equal(0.6, context.Hits[0].ScoreComponents!["vector_score"], "Agent context score components did not deserialize.");
    Equal("defined_ancestor", context.Hits[0].ExpandedContext!["reason"].GetString() ?? string.Empty, "Agent context expanded context did not deserialize.");
    Equal("hybrid", context.Diagnostics!.Mode, "Agent context diagnostics mode did not deserialize.");
    Equal("lmstudio", context.Diagnostics.ModelProvider, "Agent context diagnostics provider did not deserialize.");
    Equal(7, context.Diagnostics.VectorHitCount, "Agent context diagnostics vector hit count did not deserialize.");
    Equal(3, context.Diagnostics.LexicalHitCount, "Agent context diagnostics lexical hit count did not deserialize.");
    Equal(2, context.Diagnostics.SummaryHitCount, "Agent context diagnostics summary hit count did not deserialize.");
    Equal(9, context.Diagnostics.VectorCandidateCount, "Agent context diagnostics vector candidate count did not deserialize.");
    Equal(5, context.Diagnostics.LexicalCandidateCount, "Agent context diagnostics lexical candidate count did not deserialize.");
    Equal(4, context.Diagnostics.SummaryCandidateCount, "Agent context diagnostics summary candidate count did not deserialize.");

    var package = JsonSerializer.Deserialize<AgentContextPackageResult>(
        """
        {
          "query": {
            "query": "DownloadAsync",
            "repository_id": "repo:test",
            "limit": 3,
            "max_characters": 4000,
            "kinds": ["Method"],
            "filters": {"project": "Sample"},
            "vector": [0.1, 0.2],
            "context_depth": 3,
            "include_content": true,
            "include_relationships": true,
            "relationship_limit": 8,
            "caller_limit": 2,
            "callee_limit": 2,
            "read_limit": 1,
            "write_limit": 1,
            "contains_limit": 1,
            "definition_limit": 1,
            "uses_type_limit": 0,
            "include_repository": true
          },
          "repository": {"repository_id": "repo:test", "alias": "sample_repo"},
          "latest_run": {"run_id": "run:test", "embedding_provider": "lmstudio"},
          "items": [
            {
              "hit": {
                "node_id": "node:download",
                "stable_key": "stable:download",
                "kind": "Method",
                "file_path": "Downloader.cs",
                "start_line": 10,
                "end_line": 20,
                "score": 0.91
              },
              "node": {"id": "node:download", "kind": "Method"},
              "content": {"hash": "content:download"},
              "summary": {"summary": "Downloads subtitles for a video URL.", "provider": "test"},
              "snippet": "return Task.CompletedTask;",
              "relationships": [{"kind": "Invokes", "target_node_id": "node:callee"}],
              "relationship_groups": {
                "callees": [{"kind": "Invokes", "target_node_id": "node:callee"}],
                "callers": []
              },
              "rationale": {"rank": 1, "expanded": true}
            }
          ],
          "total_snippet_characters": 26,
          "generated_at": "2026-06-06T10:00:00Z"
        }
        """,
        options);

    NotNull(package, "Agent context package did not deserialize.");
    Equal(4000, package!.Query.MaxCharacters, "Agent context package max characters did not deserialize.");
    Equal(0, package.Query.UsesTypeLimit ?? -1, "Agent context package uses type limit did not deserialize.");
    Equal("sample_repo", package.Repository!["alias"].GetString() ?? string.Empty, "Agent context package repository metadata did not deserialize.");
    Equal("lmstudio", package.LatestRun!["embedding_provider"].GetString() ?? string.Empty, "Agent context package latest run did not deserialize.");
    Equal("Downloads subtitles for a video URL.", package.Items[0].Summary!["summary"].GetString() ?? string.Empty, "Agent context package summary did not deserialize.");
    Equal("return Task.CompletedTask;", package.Items[0].Snippet ?? string.Empty, "Agent context package snippet did not deserialize.");
    Equal("node:callee", package.Items[0].RelationshipGroups!["callees"][0]["target_node_id"].GetString() ?? string.Empty, "Agent context package relationship groups did not deserialize.");
    Equal(1, package.Items[0].Rationale!["rank"].GetInt32(), "Agent context package rationale did not deserialize.");

    return Task.CompletedTask;
}

static async Task TestAgentAccessClientCallsRestEndpoints()
{
    var handler = new FakeAgentAccessHandler();
    using var http = new HttpClient(handler)
    {
        BaseAddress = new Uri("http://agent.test/")
    };
    var client = new AgentAccessClient(http);

    var health = await client.GetHealthAsync();
    Equal("health", handler.Requests[0].Path, "Agent Access health path changed.");
    Equal("healthy", health.Status, "Agent Access health status did not deserialize.");
    Equal("healthy", health.Components["model_provider"].GetProperty("status").GetString() ?? string.Empty, "Agent Access health components did not deserialize.");

    var status = await client.GetStatusAsync();
    Equal("status", handler.Requests[1].Path, "Agent Access status path changed.");
    Equal("codemesh-agent-access", status.Service, "Agent Access status service did not deserialize.");

    var context = await client.SearchContextAsync(new AgentContextQuery(
        "DownloadAsync",
        RepositoryId: "repo:test",
        Kinds: ["Method"],
        Filters: new Dictionary<string, string> { ["project"] = "Sample" },
        Vector: [0.1f, 0.2f],
        IncludeContextRelationships: true));

    Equal("context/search", handler.Requests[2].Path, "Agent Access context search path changed.");
    if (!handler.Requests[2].Body.Contains("\"repository_id\":\"repo:test\"", StringComparison.Ordinal) ||
        !handler.Requests[2].Body.Contains("\"include_context_relationships\":true", StringComparison.Ordinal))
    {
        throw new InvalidOperationException("Agent Access context request did not use REST JSON field names.");
    }

    Equal("hybrid", context.Diagnostics!.Mode, "Agent Access context response diagnostics changed.");
    Equal("node:download", context.Hits[0].NodeId, "Agent Access context hit did not deserialize.");

    var package = await client.GetContextPackageAsync(new AgentContextPackageQuery(
        "DownloadAsync",
        RepositoryId: "repo:test",
        MaxCharacters: 4000,
        CallerLimit: 2));

    Equal("context/package", handler.Requests[3].Path, "Agent Access context package path changed.");
    if (!handler.Requests[3].Body.Contains("\"max_characters\":4000", StringComparison.Ordinal) ||
        !handler.Requests[3].Body.Contains("\"caller_limit\":2", StringComparison.Ordinal))
    {
        throw new InvalidOperationException("Agent Access package request did not use REST JSON field names.");
    }

    Equal("return Task.CompletedTask;", package.Items[0].Snippet ?? string.Empty, "Agent Access package response did not deserialize.");

    var symbols = await client.SearchSymbolsAsync(new AgentSymbolQuery(
        "DownloadAsync",
        RepositoryId: "repo:test",
        Kinds: ["Method"],
        IncludeDeclarations: false));

    Equal("symbols/search", handler.Requests[4].Path, "Agent Access symbol search path changed.");
    Equal("DownloadAsync", symbols.Symbols[0].Node["name"].GetString() ?? string.Empty, "Agent Access symbol result did not deserialize.");

    var node = await client.GetNodeAsync(new AgentNodeLookup(
        "node:download",
        RepositoryId: "repo:test",
        IncludeContent: false));

    Equal("nodes/get", handler.Requests[5].Path, "Agent Access node path changed.");
    Equal("node:download", node.Node!["id"].GetString() ?? string.Empty, "Agent Access node result did not deserialize.");

    var neighbors = await client.GetNeighborsAsync(new AgentNeighborQuery(
        "node:download",
        RepositoryId: "repo:test",
        RelationshipKinds: ["Invokes"]));

    Equal("graph/neighbors", handler.Requests[6].Path, "Agent Access neighbors path changed.");
    Equal("node:download", neighbors.Node!["id"].GetString() ?? string.Empty, "Agent Access neighbor node did not deserialize.");
    Equal("Invokes", neighbors.Relationships[0]["kind"].GetString() ?? string.Empty, "Agent Access neighbor result did not deserialize.");

    var repositories = await client.ListRepositoriesAsync(limit: 3);
    Equal("repositories?limit=3", handler.Requests[7].Path, "Agent Access repositories path changed.");
    Equal("sample_repo", repositories.Repositories[0].Alias ?? string.Empty, "Agent Access repository list did not deserialize.");
    Equal(17, repositories.Repositories[0].NodeCount, "Agent Access repository node count did not deserialize.");

    var repository = await client.GetRepositoryAsync("sample repo/id");
    Equal("repositories/sample%20repo%2Fid", handler.Requests[8].Path, "Agent Access repository lookup path did not escape id.");
    Equal("repo:test", repository!.RepositoryId, "Agent Access repository lookup did not deserialize.");

    var coverage = await client.GetSummaryCoverageAsync("sample repo/id");
    Equal("repositories/sample%20repo%2Fid/summaries", handler.Requests[9].Path, "Agent Access summary coverage path did not escape id.");
        Equal(5, coverage.CompletedCount, "Agent Access summary coverage completed count did not deserialize.");
        Equal(2, coverage.KindCounts["Method"], "Agent Access summary coverage kind counts did not deserialize.");
        Equal("qwen/qwen2.5-coder-14b", coverage.ProviderModelCountDetails[0].Model, "Agent Access summary coverage provider/model details did not deserialize.");
        Equal("model failed", coverage.RecentFailures[0]["error"].GetString() ?? string.Empty, "Agent Access summary coverage failures did not deserialize.");

    var runs = await client.ListIngestionRunsAsync(repositoryId: "sample repo/id", limit: 2);
    Equal("ingestion-runs?limit=2&repository_id=sample%20repo%2Fid", handler.Requests[10].Path, "Agent Access runs path changed.");
    Equal("run:test", runs.Runs[0].RunId, "Agent Access ingestion run did not deserialize.");
    Equal("lmstudio", runs.Runs[0].EmbeddingProvider, "Agent Access run embedding provider did not deserialize.");

    var delete = await client.DeleteRepositoryAsync("sample repo/id");
    Equal(HttpMethod.Delete.Method, handler.Requests[11].Method, "Agent Access repository delete method changed.");
    Equal("repositories/sample%20repo%2Fid", handler.Requests[11].Path, "Agent Access repository delete path did not escape id.");
    Equal("repo:test", delete.RepositoryId, "Agent Access repository delete response did not deserialize.");
    Equal(true, delete.Deleted, "Agent Access repository delete did not report deletion.");
    Equal(true, delete.SummariesCleaned, "Agent Access repository delete cleanup flags did not deserialize.");

    handler.FailNextRequest = true;
    try
    {
        await client.SearchContextAsync(new AgentContextQuery("DownloadAsync"));
    }
    catch (InvalidOperationException exception) when (
        exception.Message.Contains("context/search", StringComparison.Ordinal) &&
        exception.Message.Contains("HTTP 503", StringComparison.Ordinal))
    {
        return;
    }

    throw new InvalidOperationException("Agent Access client did not surface REST error details.");
}

static async Task TestIngestionWritesParserOutput()
{
    var store = new InMemoryCodeMeshStore();
    var parser = new FakeParserClient();
    var orchestrator = new IngestionOrchestrator(
        parser,
        store,
        store,
        store,
        new NoEmbeddingProvider());

    var result = await orchestrator.IngestAsync(new IngestionRequest(
        Directory.GetCurrentDirectory(),
        DryRun: false));

    Equal(1, result.NodeCount, "Expected one node from fake parser.");
    Equal(1, result.ContentCount, "Expected one content item from fake parser.");

    var node = await store.GetNodeAsync(FakeParserClient.NodeId);
    NotNull(node, "Node was not written to graph store.");

    var content = await store.GetContentAsync(FakeParserClient.ContentHash);
    NotNull(content, "Content was not written to content store.");
}

static async Task TestDryRunSkipsStores()
{
    var store = new InMemoryCodeMeshStore();
    var parser = new FakeParserClient();
    var orchestrator = new IngestionOrchestrator(
        parser,
        store,
        store,
        store,
        new NoEmbeddingProvider());

    var result = await orchestrator.IngestAsync(new IngestionRequest(
        Directory.GetCurrentDirectory(),
        DryRun: true));

    Equal(1, result.NodeCount, "Dry run should still parse nodes.");

    var node = await store.GetNodeAsync(FakeParserClient.NodeId);
    IsNull(node, "Dry run wrote to graph store.");

    var content = await store.GetContentAsync(FakeParserClient.ContentHash);
    IsNull(content, "Dry run wrote to content store.");
}

static async Task TestRepositoryRefreshRemovesStaleRecords()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-refresh-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        var store = new InMemoryCodeMeshStore();
        var parser = new RefreshParserClient("Alpha");
        var orchestrator = new IngestionOrchestrator(
            parser,
            store,
            store,
            store,
            new DeterministicEmbeddingProvider());
        var repositoryId = CodeMeshHash.StableId(Path.GetFullPath(root));

        await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: false));

        var alphaNode = await store.GetNodeAsync(RefreshParserClient.NodeIdFor("Alpha"));
        NotNull(alphaNode, "Initial refresh ingest did not write Alpha node.");
        Equal(repositoryId, alphaNode!.Metadata["repositoryId"], "Repository id metadata was not stamped.");
        NotNull(await store.GetContentAsync(RefreshParserClient.ContentHashFor("Alpha")), "Initial refresh ingest did not write Alpha content.");

        parser.TypeName = "Beta";
        await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: false));

        IsNull(await store.GetNodeAsync(RefreshParserClient.NodeIdFor("Alpha")), "Refresh did not remove stale Alpha node.");
        IsNull(await store.GetContentAsync(RefreshParserClient.ContentHashFor("Alpha")), "Refresh did not remove stale Alpha content.");
        NotNull(await store.GetNodeAsync(RefreshParserClient.NodeIdFor("Beta")), "Refresh did not keep current Beta node.");
        NotNull(await store.GetContentAsync(RefreshParserClient.ContentHashFor("Beta")), "Refresh did not keep current Beta content.");

        var matches = await store.SearchAsync(
            [1.0f, 0.0f],
            10,
            new Dictionary<string, string> { ["repositoryId"] = repositoryId });
        if (matches.Any(match => string.Equals(match.NodeId, RefreshParserClient.NodeIdFor("Alpha"), StringComparison.Ordinal)))
        {
            throw new InvalidOperationException("Refresh did not remove stale Alpha embedding.");
        }

        if (!matches.Any(match => string.Equals(match.NodeId, RefreshParserClient.NodeIdFor("Beta"), StringComparison.Ordinal)))
        {
            throw new InvalidOperationException("Refresh did not keep current Beta embedding.");
        }
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestIncrementalIngestionSkipsUnchangedRecords()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-incremental-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        var store = new InMemoryCodeMeshStore();
        var parser = new RefreshParserClient("Alpha");
        var embeddingProvider = new CountingEmbeddingProvider();
        var orchestrator = new IngestionOrchestrator(
            parser,
            store,
            store,
            store,
            embeddingProvider);

        var first = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: false));

        NotNull(first.Stats, "Initial ingest did not report stats.");
        Equal(1, first.Stats!.WrittenNodeCount, "Initial ingest did not write the parsed node.");
        Equal(0, first.Stats.SkippedNodeCount, "Initial ingest incorrectly skipped a node.");
        Equal(1, first.Stats.WrittenContentCount, "Initial ingest did not write content.");
        Equal(1, first.Stats.WrittenEmbeddingCount, "Initial ingest did not write an embedding.");
        Equal(1, embeddingProvider.EmbeddedNodeCount, "Initial ingest did not call embedding provider for the parsed node.");

        var second = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: false));

        NotNull(second.Stats, "Incremental ingest did not report stats.");
        Equal(1, second.Stats!.ParsedNodeCount, "Incremental ingest parsed node count changed.");
        Equal(0, second.Stats.WrittenNodeCount, "Incremental ingest rewrote an unchanged node.");
        Equal(1, second.Stats.SkippedNodeCount, "Incremental ingest did not skip the unchanged node.");
        Equal(0, second.Stats.WrittenContentCount, "Incremental ingest rewrote unchanged content.");
        Equal(1, second.Stats.SkippedContentCount, "Incremental ingest did not skip unchanged content.");
        Equal(0, second.Stats.WrittenEmbeddingCount, "Incremental ingest regenerated an unchanged embedding.");
        Equal(1, second.Stats.SkippedEmbeddingCount, "Incremental ingest did not skip the unchanged embedding.");
        Equal(1, embeddingProvider.EmbeddedNodeCount, "Incremental ingest called embedding provider for an unchanged node.");
        NotNull(await store.GetNodeAsync(RefreshParserClient.NodeIdFor("Alpha")), "Incremental cleanup removed an unchanged node.");
        NotNull(await store.GetContentAsync(RefreshParserClient.ContentHashFor("Alpha")), "Incremental cleanup removed unchanged content.");

        parser.TypeName = "Beta";
        var third = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: false));

        NotNull(third.Stats, "Changed incremental ingest did not report stats.");
        Equal(1, third.Stats!.WrittenNodeCount, "Changed incremental ingest did not write the new node.");
        Equal(0, third.Stats.SkippedNodeCount, "Changed incremental ingest incorrectly skipped the new node.");
        Equal(2, embeddingProvider.EmbeddedNodeCount, "Changed incremental ingest did not embed the changed node.");
        IsNull(await store.GetNodeAsync(RefreshParserClient.NodeIdFor("Alpha")), "Incremental cleanup did not remove stale Alpha node.");
        NotNull(await store.GetNodeAsync(RefreshParserClient.NodeIdFor("Beta")), "Incremental cleanup did not keep current Beta node.");
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestIncrementalIngestionSkipsUnchangedSummaries()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-summary-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        var store = new InMemoryCodeMeshStore();
        var parser = new RefreshParserClient("Alpha");
        var summaryProvider = new CountingSummaryProvider();
        var orchestrator = new IngestionOrchestrator(
            parser,
            store,
            store,
            store,
            new NoEmbeddingProvider(),
            summaryStore: store,
            summaryProvider: summaryProvider);
        var repositoryId = CodeMeshHash.StableId(Path.GetFullPath(root));

        var first = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            IncludeSummaries: true));

        Equal(1, first.SummaryCount, "Initial ingest did not write a summary.");
        Equal(1, first.Stats?.SummaryCandidateCount ?? -1, "Initial ingest summary candidate count changed.");
        Equal(1, first.Stats?.WrittenSummaryCount ?? -1, "Initial ingest did not report a written summary.");
        Equal(1, summaryProvider.SummarizedNodeCount, "Initial ingest did not call summary provider.");

        var states = await store.GetSummaryStatesAsync(repositoryId);
        Equal(1, states.Count, "Summary store did not retain the generated summary.");
        Equal(RefreshParserClient.NodeIdFor("Alpha"), states[0].NodeId, "Summary state node id changed.");
        var coverage = await store.GetSummaryCoverageAsync(repositoryId);
        Equal(1, coverage.TotalCount, "Summary coverage total count changed.");
        Equal(1, coverage.CompletedCount, "Summary coverage completed count changed.");
        Equal(0, coverage.FailedCount, "Summary coverage failed count changed.");
        Equal(1, coverage.KindCounts["Class"], "Summary coverage kind count changed.");
        Equal(1, coverage.ProviderModelCounts["test/summary-counting/node-summary-v1"], "Summary coverage provider/model count changed.");
        Equal("summary-counting", coverage.ProviderModelCountDetails[0].Model, "Summary coverage provider/model detail changed.");

        await store.UpsertSummariesAsync([
            new CodeNodeSummary(
                CodeMeshHash.StableId(
                    "summary",
                    repositoryId,
                    RefreshParserClient.NodeIdFor("Alpha"),
                    states[0].ContentHash,
                    "symbol",
                    "other",
                    "other-model",
                    "node-summary-v1"),
                repositoryId,
                Path.GetFullPath(root),
                "run:other-summary",
                RefreshParserClient.NodeIdFor("Alpha"),
                RefreshParserClient.NodeIdFor("Alpha"),
                CodeNodeKind.Class,
                "Alpha",
                "csharp",
                "Sample",
                new SourceSpan("Alpha.cs", 1, 1, 1, 1),
                states[0].ContentHash,
                "symbol",
                "Alternate provider summary.",
                [],
                "high",
                "other",
                "other-model",
                "node-summary-v1",
                CodeMeshHash.StableId("summary-prompt", "node-summary-v1"),
                DateTimeOffset.UtcNow,
                "completed",
                null,
                new Dictionary<string, string>())
        ]);

        var second = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            IncludeSummaries: true));

        Equal(0, second.SummaryCount, "Unchanged ingest should not rewrite a summary.");
        Equal(0, second.Stats?.WrittenSummaryCount ?? -1, "Unchanged ingest rewrote a summary.");
        Equal(1, second.Stats?.SkippedSummaryCount ?? -1, "Unchanged ingest did not skip the existing summary.");
        Equal(1, summaryProvider.SummarizedNodeCount, "Unchanged ingest called summary provider again.");

        var forced = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            IncludeSummaries: true,
            ForceSummaries: true));

        Equal(1, forced.SummaryCount, "Forced ingest did not rewrite summary.");
        Equal(1, forced.Stats?.WrittenSummaryCount ?? -1, "Forced ingest did not report a written summary.");
        Equal(0, forced.Stats?.SkippedSummaryCount ?? -1, "Forced ingest incorrectly skipped summary.");
        Equal(2, summaryProvider.SummarizedNodeCount, "Forced ingest did not call summary provider again.");
        coverage = await store.GetSummaryCoverageAsync(repositoryId);
        Equal(2, coverage.TotalCount, "Forced summary cleanup removed current summaries from another provider/model.");
        Equal(1, coverage.ProviderModelCounts["other/other-model/node-summary-v1"], "Forced summary cleanup did not keep alternate provider summary.");

        parser.TypeName = "Beta";
        var changedWithoutSummaries = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            IncludeSummaries: false));

        Equal(0, changedWithoutSummaries.SummaryCount, "Summary-disabled changed ingest should not write summaries.");
        Equal(2, summaryProvider.SummarizedNodeCount, "Summary-disabled changed ingest called the summary provider.");
        coverage = await store.GetSummaryCoverageAsync(repositoryId);
        Equal(0, coverage.TotalCount, "Summary-disabled changed ingest did not remove stale summaries across providers.");
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestForcedEmbeddingIngestionRebuildsUnchangedEmbeddings()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-force-embeddings-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        var store = new InMemoryCodeMeshStore();
        var parser = new RefreshParserClient("Alpha");
        var embeddingProvider = new CountingEmbeddingProvider();
        var orchestrator = new IngestionOrchestrator(
            parser,
            store,
            store,
            store,
            embeddingProvider);

        await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: false));
        var second = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: false));
        Equal(0, second.Stats?.WrittenEmbeddingCount ?? -1, "Unchanged ingestion should not rewrite embeddings before force mode.");
        Equal(1, second.Stats?.SkippedEmbeddingCount ?? -1, "Unchanged ingestion should skip the existing embedding before force mode.");
        Equal(1, embeddingProvider.EmbeddedNodeCount, "Unchanged ingestion called the embedding provider before force mode.");

        var forced = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: false,
            ForceEmbeddings: true));

        Equal(1, forced.Stats?.WrittenEmbeddingCount ?? -1, "Forced ingestion did not rewrite the unchanged embedding.");
        Equal(0, forced.Stats?.SkippedEmbeddingCount ?? -1, "Forced ingestion incorrectly skipped an unchanged embedding.");
        Equal(2, embeddingProvider.EmbeddedNodeCount, "Forced ingestion did not call the embedding provider again.");
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestEmbeddingVerifierReportsMissingAndStaleVectors()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-verify-embeddings-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        var store = new InMemoryCodeMeshStore();
        var parser = new RefreshParserClient("Alpha");
        var embeddingProvider = new CountingEmbeddingProvider();
        var orchestrator = new IngestionOrchestrator(
            parser,
            store,
            store,
            store,
            embeddingProvider);
        var result = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: false));
        var verifier = new EmbeddingVerifier(store, store);

        var complete = await verifier.VerifyAsync(new EmbeddingVerificationRequest(
            result.Repository.Id,
            embeddingProvider.Provider,
            embeddingProvider.Model));
        Equal(true, complete.IsComplete, "Verifier did not report complete embeddings after ingestion.");
        Equal(1, complete.ExpectedCount, "Verifier expected node count changed.");
        Equal(1, complete.CurrentEmbeddingCount, "Verifier current embedding count changed.");

        await store.RemoveEmbeddingsExceptAsync(result.Repository.Id, new HashSet<string>(StringComparer.Ordinal));
        await store.UpsertEmbeddingsAsync([
            new EmbeddingRecord(
                "embedding:stale",
                "csharp:type:Sample.Stale",
                "stale-content",
                embeddingProvider.Provider,
                embeddingProvider.Model,
                2,
                [1.0f, 0.0f],
                new Dictionary<string, string>
                {
                    ["repositoryId"] = result.Repository.Id,
                    ["preview"] = "stale"
                })
        ]);

        var incomplete = await verifier.VerifyAsync(new EmbeddingVerificationRequest(
            result.Repository.Id,
            embeddingProvider.Provider,
            embeddingProvider.Model));
        Equal(false, incomplete.IsComplete, "Verifier did not report incomplete embeddings.");
        Equal(1, incomplete.MissingCount, "Verifier did not report the missing current embedding.");
        Equal(1, incomplete.StaleCount, "Verifier did not report the stale embedding.");

        var missingRepository = await verifier.VerifyAsync(new EmbeddingVerificationRequest(
            "missing-repository",
            embeddingProvider.Provider,
            embeddingProvider.Model));
        Equal(false, missingRepository.IsComplete, "Verifier incorrectly reported a missing repository as complete.");
        Equal("empty_graph", missingRepository.Issues[0].Kind, "Verifier did not report an empty graph inventory.");
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestRepositoryCleanupRemovesIndexedData()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-cleanup-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        var store = new InMemoryCodeMeshStore();
        var parser = new RefreshParserClient("Alpha");
        var embeddingProvider = new CountingEmbeddingProvider();
        var summaryProvider = new CountingSummaryProvider();
        var orchestrator = new IngestionOrchestrator(
            parser,
            store,
            store,
            store,
            embeddingProvider,
            store,
            store,
            summaryProvider);
        var result = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: false,
            IncludeSummaries: true));

        var repositoryId = result.Repository.Id;
        NotNull(await store.GetNodeAsync(RefreshParserClient.NodeIdFor("Alpha")), "Cleanup setup did not write a graph node.");
        NotNull(await store.GetContentAsync(RefreshParserClient.ContentHashFor("Alpha")), "Cleanup setup did not write content.");
        Equal(1, (await store.GetEmbeddingStatesAsync(repositoryId)).Count, "Cleanup setup did not write an embedding.");
        Equal(1, (await store.GetSummaryStatesAsync(repositoryId)).Count, "Cleanup setup did not write a summary.");
        NotNull(await store.GetRepositoryAsync(repositoryId), "Cleanup setup did not write repository metadata.");
        Equal(1, (await store.ListRunsAsync(repositoryId)).Count, "Cleanup setup did not write an ingestion run.");

        var cleanup = new RepositoryCleanupService(
            store,
            store,
            store,
            store,
            store);
        var cleanupResult = await cleanup.DeleteRepositoryAsync(repositoryId);

        Equal(repositoryId, cleanupResult.RepositoryId, "Cleanup result repository id changed.");
        Equal(true, cleanupResult.RegistryEntryExisted, "Cleanup did not find the registry entry.");
        Equal(true, cleanupResult.GraphCleaned, "Cleanup did not report graph cleanup.");
        Equal(true, cleanupResult.ContentCleaned, "Cleanup did not report content cleanup.");
        Equal(true, cleanupResult.EmbeddingsCleaned, "Cleanup did not report embedding cleanup.");
        Equal(true, cleanupResult.SummariesCleaned, "Cleanup did not report summary cleanup.");
        IsNull(await store.GetNodeAsync(RefreshParserClient.NodeIdFor("Alpha")), "Cleanup did not remove graph node.");
        IsNull(await store.GetContentAsync(RefreshParserClient.ContentHashFor("Alpha")), "Cleanup did not remove content.");
        Equal(0, (await store.GetContentStatesAsync(repositoryId)).Count, "Cleanup left content state behind.");
        Equal(0, (await store.GetEmbeddingStatesAsync(repositoryId)).Count, "Cleanup left embeddings behind.");
        Equal(0, (await store.GetSummaryStatesAsync(repositoryId)).Count, "Cleanup left summaries behind.");
        IsNull(await store.GetRepositoryAsync(repositoryId), "Cleanup did not remove repository metadata.");
        Equal(0, (await store.ListRunsAsync(repositoryId)).Count, "Cleanup did not remove ingestion runs.");

        var matches = await store.SearchAsync(
            [1.0f, 0.0f],
            10,
            new Dictionary<string, string> { ["repositoryId"] = repositoryId });
        Equal(0, matches.Count, "Cleanup left searchable embeddings behind.");
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestRepositoryAliasesAreGeneratedAndResolved()
{
    Equal("youtube_downloader", RepositoryAlias.Normalize("YoutubeDownloader"), "Repository alias PascalCase normalization changed.");
    Equal("youtube_downloader", RepositoryAlias.Normalize("youtube-downloader"), "Repository alias separator normalization changed.");

    var root = Path.Combine(Path.GetTempPath(), "YoutubeDownloader");
    Directory.CreateDirectory(root);

    try
    {
        var store = new InMemoryCodeMeshStore();
        var orchestrator = new IngestionOrchestrator(
            new FakeParserClient(),
            store,
            store,
            store,
            new NoEmbeddingProvider(),
            store);

        var result = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: true));

        var loadedById = await store.GetRepositoryAsync(result.Repository.Id);
        NotNull(loadedById, "Registry did not load repository by id.");
        Equal("youtube_downloader", loadedById!.Alias ?? string.Empty, "Registry alias changed.");
        Equal("youtube_downloader", loadedById.Metadata["alias"], "Registry alias metadata changed.");

        var loadedByAlias = await store.GetRepositoryAsync("youtube_downloader");
        NotNull(loadedByAlias, "Registry did not load repository by alias.");
        Equal(result.Repository.Id, loadedByAlias!.RepositoryId, "Registry alias resolved to the wrong repository id.");
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestIngestionWritesRepositoryRegistryRecords()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-registry-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        var store = new InMemoryCodeMeshStore();
        var orchestrator = new IngestionOrchestrator(
            new FakeParserClient(),
            store,
            store,
            store,
            new NoEmbeddingProvider(),
            store);

        var result = await orchestrator.IngestAsync(new IngestionRequest(
            root,
            DryRun: false,
            SkipEmbeddings: true));

        var repositories = await store.ListRepositoriesAsync();
        Equal(1, repositories.Count, "Registry did not record the ingested repository.");
        Equal(result.Repository.Id, repositories[0].RepositoryId, "Registry repository id changed.");
        Equal(result.Run.RunId, repositories[0].LastRunId ?? string.Empty, "Registry last run id changed.");
        Equal(IngestionStage.Completed, repositories[0].LastStage ?? IngestionStage.Failed, "Registry last stage changed.");
        Equal(1, repositories[0].NodeCount, "Registry node count changed.");
        Equal(1, repositories[0].ContentCount, "Registry content count changed.");

        var loadedRepository = await store.GetRepositoryAsync(result.Repository.Id);
        NotNull(loadedRepository, "Registry did not load the repository by id.");
        Equal(root, loadedRepository!.RootPath, "Registry repository root changed.");

        var runs = await store.ListRunsAsync(result.Repository.Id);
        Equal(1, runs.Count, "Registry did not record the ingestion run.");
        Equal(result.Run.RunId, runs[0].RunId, "Registry run id changed.");
        Equal("fake-parser", runs[0].ParserName, "Registry parser name changed.");
        Equal("none", runs[0].EmbeddingProvider, "Registry embedding provider changed.");
        Equal(1, runs[0].Stats?.ParsedNodeCount ?? 0, "Registry stats changed.");
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestStatusUsesConfiguredOllamaEndpoint()
{
    var previousUrl = Environment.GetEnvironmentVariable("CODEMESH_OLLAMA_URL");
    var previousProvider = Environment.GetEnvironmentVariable("CODEMESH_MODEL_PROVIDER");
    var previousModel = Environment.GetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL");

    await using var server = new SlowHttpServer(TimeSpan.FromMilliseconds(1100));

    try
    {
        Environment.SetEnvironmentVariable("CODEMESH_OLLAMA_URL", server.BaseUrl);
        Environment.SetEnvironmentVariable("CODEMESH_MODEL_PROVIDER", "ollama");
        Environment.SetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL", "test-embed");

        var report = await new CodeMeshStatusService()
            .GetStatusAsync(Directory.GetCurrentDirectory());
        var ollama = report.Components.Single(component => component.Name == "ollama");

        Equal(ComponentState.Healthy, ollama.State, "Status did not use the configured slow Ollama endpoint.");
        Equal($"{server.BaseUrl}/api/tags", ollama.Metadata["endpoint"], "Status did not probe the configured Ollama URL.");
        Equal("ollama", ollama.Metadata["provider"], "Status did not report the configured model provider.");
        Equal("test-embed", ollama.Metadata["model"], "Status did not report the configured embedding model.");
    }
    finally
    {
        Environment.SetEnvironmentVariable("CODEMESH_OLLAMA_URL", previousUrl);
        Environment.SetEnvironmentVariable("CODEMESH_MODEL_PROVIDER", previousProvider);
        Environment.SetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL", previousModel);
    }
}

static async Task TestStatusRetriesTransientOllamaFailures()
{
    var previousUrl = Environment.GetEnvironmentVariable("CODEMESH_OLLAMA_URL");
    var previousProvider = Environment.GetEnvironmentVariable("CODEMESH_MODEL_PROVIDER");
    var previousModel = Environment.GetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL");

    await using var server = new SlowHttpServer(TimeSpan.Zero, failuresBeforeSuccess: 1);

    try
    {
        Environment.SetEnvironmentVariable("CODEMESH_OLLAMA_URL", server.BaseUrl);
        Environment.SetEnvironmentVariable("CODEMESH_MODEL_PROVIDER", "ollama");
        Environment.SetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL", "test-embed");

        var report = await new CodeMeshStatusService()
            .GetStatusAsync(Directory.GetCurrentDirectory());
        var ollama = report.Components.Single(component => component.Name == "ollama");

        Equal(ComponentState.Healthy, ollama.State, "Status did not retry a transient Ollama probe failure.");
        if (server.RequestCount < 2)
        {
            throw new InvalidOperationException("Status did not issue a retry after the transient Ollama failure.");
        }
    }
    finally
    {
        Environment.SetEnvironmentVariable("CODEMESH_OLLAMA_URL", previousUrl);
        Environment.SetEnvironmentVariable("CODEMESH_MODEL_PROVIDER", previousProvider);
        Environment.SetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL", previousModel);
    }
}

static async Task TestStatusDegradesWhenConfiguredModelIsMissing()
{
    var previousUrl = Environment.GetEnvironmentVariable("CODEMESH_LM_STUDIO_URL");
    var previousProvider = Environment.GetEnvironmentVariable("CODEMESH_MODEL_PROVIDER");
    var previousModel = Environment.GetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL");

    await using var server = new SlowHttpServer(
        TimeSpan.Zero,
        responseBody: """{"data":[{"id":"other-model"}]}""");

    try
    {
        Environment.SetEnvironmentVariable("CODEMESH_LM_STUDIO_URL", server.BaseUrl);
        Environment.SetEnvironmentVariable("CODEMESH_MODEL_PROVIDER", "lmstudio");
        Environment.SetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL", "expected-model");

        var report = await new CodeMeshStatusService()
            .GetStatusAsync(Directory.GetCurrentDirectory());
        var lmStudio = report.Components.Single(component => component.Name == "lmstudio");

        Equal(ComponentState.Degraded, lmStudio.State, "Status did not degrade when the configured model was missing.");
        Equal($"{server.BaseUrl}/models", lmStudio.Metadata["endpoint"], "Status did not probe the configured LM Studio URL.");
        Equal("lmstudio", lmStudio.Metadata["provider"], "Status did not report the configured LM Studio provider.");
        Equal("expected-model", lmStudio.Metadata["model"], "Status did not report the configured LM Studio model.");
        Equal(
            "Configured embedding model is not listed by the model provider.",
            lmStudio.Metadata["detail"],
            "Status did not report the missing model detail.");
    }
    finally
    {
        Environment.SetEnvironmentVariable("CODEMESH_LM_STUDIO_URL", previousUrl);
        Environment.SetEnvironmentVariable("CODEMESH_MODEL_PROVIDER", previousProvider);
        Environment.SetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL", previousModel);
    }
}

static async Task TestOllamaEmbeddingProviderMapsResponses()
{
    var handler = new FakeOllamaEmbeddingHandler();
    using var http = new HttpClient(handler)
    {
        BaseAddress = new Uri("http://ollama.test/")
    };
    using var provider = new OllamaEmbeddingProvider(http, "test-embed", batchSize: 2);

    var text = "public sealed class EmbeddedSmoke { }";
    var hash = CodeMeshHash.Sha256Hex(text);
    var node = new CodeNode(
        "csharp:type:CodeMesh.Tests.EmbeddedSmoke",
        "csharp:type:CodeMesh.Tests.EmbeddedSmoke",
        CodeNodeKind.Class,
        "EmbeddedSmoke",
        "csharp",
        "CodeMesh.Tests",
        new SourceSpan("EmbeddedSmoke.cs", 1, 1, 1, 37),
        hash,
        new Dictionary<string, string>());
    var content = new CodeContent(
        hash,
        text,
        "text/x-csharp-fragment",
        DateTimeOffset.UtcNow,
        DateTimeOffset.UtcNow);

    var embeddings = await provider.EmbedAsync(
        [node],
        new Dictionary<string, CodeContent> { [hash] = content });

    Equal(1, handler.RequestCount, "Expected one Ollama embed request.");
    Equal(1, embeddings.Count, "Expected one embedding record.");
    Equal("ollama", embeddings[0].Provider, "Ollama provider name changed.");
    Equal("test-embed", embeddings[0].Model, "Ollama embedding model changed.");
    Equal(node.Id, embeddings[0].NodeId, "Ollama embedding node id changed.");
    Equal(hash, embeddings[0].ContentHash, "Ollama embedding content hash changed.");
    Equal(3, embeddings[0].Dimensions, "Ollama embedding dimensions changed.");
    Equal("Class", embeddings[0].Metadata["kind"], "Ollama embedding kind metadata changed.");
    Equal("EmbeddedSmoke.cs", embeddings[0].Metadata["filePath"], "Ollama embedding file path metadata changed.");
    if (!handler.LastRequestBody.Contains("search_document: public sealed class EmbeddedSmoke", StringComparison.Ordinal))
    {
        throw new InvalidOperationException("Ollama embedding request was not prefixed for document retrieval.");
    }
}

static async Task TestLmStudioEmbeddingProviderMapsResponses()
{
    var handler = new FakeLmStudioEmbeddingHandler();
    using var http = new HttpClient(handler)
    {
        BaseAddress = new Uri("http://lmstudio.test/v1/")
    };
    using var provider = new LmStudioEmbeddingProvider(http, "test-embed", batchSize: 2);

    var text = "public sealed class EmbeddedSmoke { }";
    var hash = CodeMeshHash.Sha256Hex(text);
    var node = new CodeNode(
        "csharp:type:CodeMesh.Tests.EmbeddedSmoke",
        "csharp:type:CodeMesh.Tests.EmbeddedSmoke",
        CodeNodeKind.Class,
        "EmbeddedSmoke",
        "csharp",
        "CodeMesh.Tests",
        new SourceSpan("EmbeddedSmoke.cs", 1, 1, 1, 37),
        hash,
        new Dictionary<string, string>());
    var content = new CodeContent(
        hash,
        text,
        "text/x-csharp-fragment",
        DateTimeOffset.UtcNow,
        DateTimeOffset.UtcNow);

    var embeddings = await provider.EmbedAsync(
        [node],
        new Dictionary<string, CodeContent> { [hash] = content });

    Equal(1, handler.RequestCount, "Expected one LM Studio embedding request.");
    Equal(1, embeddings.Count, "Expected one embedding record.");
    Equal("lmstudio", embeddings[0].Provider, "LM Studio provider name changed.");
    Equal("test-embed", embeddings[0].Model, "LM Studio embedding model changed.");
    Equal(node.Id, embeddings[0].NodeId, "LM Studio embedding node id changed.");
    Equal(hash, embeddings[0].ContentHash, "LM Studio embedding content hash changed.");
    Equal(3, embeddings[0].Dimensions, "LM Studio embedding dimensions changed.");
    Equal("Class", embeddings[0].Metadata["kind"], "LM Studio embedding kind metadata changed.");
    Equal("EmbeddedSmoke.cs", embeddings[0].Metadata["filePath"], "LM Studio embedding file path metadata changed.");
    if (!handler.LastRequestBody.Contains("search_document: public sealed class EmbeddedSmoke", StringComparison.Ordinal))
    {
        throw new InvalidOperationException("LM Studio embedding request was not prefixed for document retrieval.");
    }
}

static async Task TestLmStudioSummaryProviderAcceptsNumericConfidence()
{
    var handler = new FakeLmStudioSummaryHandler();
    using var http = new HttpClient(handler)
    {
        BaseAddress = new Uri("http://lmstudio.test/v1/")
    };
    using var provider = new LmStudioCodeSummaryProvider(http, "test-summary");

    const string text = "public static string Normalize(string url) => url.Trim().ToLowerInvariant();";
    var hash = CodeMeshHash.Sha256Hex(text);
    var node = new CodeNode(
        "csharp:method:CodeMesh.Tests.EmbeddedSmoke.Normalize(System.String)",
        "csharp:method:CodeMesh.Tests.EmbeddedSmoke.Normalize(System.String)",
        CodeNodeKind.Method,
        "Normalize",
        "csharp",
        "CodeMesh.Tests",
        new SourceSpan("EmbeddedSmoke.cs", 1, 1, 1, 72),
        hash,
        new Dictionary<string, string>());
    var content = new CodeContent(
        hash,
        text,
        "text/x-csharp-fragment",
        DateTimeOffset.UtcNow,
        DateTimeOffset.UtcNow);

    var summary = await provider.SummarizeAsync(new CodeSummaryRequest(
        node,
        content,
        "node-summary-v1",
        1500));

    Equal(1, handler.RequestCount, "Expected one LM Studio summary request.");
    Equal("lmstudio", provider.Provider, "LM Studio summary provider name changed.");
    Equal("test-summary", provider.Model, "LM Studio summary model changed.");
    Equal(
        "Trims a URL and converts it to lowercase.",
        summary.Summary,
        "LM Studio summary text did not deserialize.");
    Equal("high", summary.Confidence, "LM Studio numeric confidence was not normalized.");
    Equal("normalization", summary.Tags[0], "LM Studio summary tags did not deserialize.");
    if (!handler.LastRequestBody.Contains("\"response_format\":{\"type\":\"text\"}", StringComparison.Ordinal))
    {
        throw new InvalidOperationException("LM Studio summary request response format changed.");
    }
}

static async Task TestMongoContentStoreRoundTripsContent()
{
    var store = new MongoContentStore(new MongoContentStoreOptions(
        Environment.GetEnvironmentVariable("CODEMESH_MONGO_URI") ?? "mongodb://127.0.0.1:27017",
        Environment.GetEnvironmentVariable("CODEMESH_MONGO_TEST_DATABASE") ?? "codemesh_tests",
        Environment.GetEnvironmentVariable("CODEMESH_MONGO_TEST_CONTENT_COLLECTION") ?? "content_smoke",
        TimeSpan.FromSeconds(2)));

    using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
    var health = await store.CheckAsync(timeout.Token);
    if (health.State != CodeMesh.Domain.Health.ComponentState.Healthy)
    {
        var detail = health.Metadata.TryGetValue("detail", out var value) ? value : health.Message;
        throw new SkipTestException($"MongoDB is not reachable: {detail}");
    }

    var text = "public sealed class MongoSmoke { }";
    var now = DateTimeOffset.UtcNow;
    var content = new CodeContent(
        CodeMeshHash.Sha256Hex(text),
        text,
        "text/x-csharp-fragment",
        now,
        now);

    await store.UpsertContentAsync(content, timeout.Token);
    var loaded = await store.GetContentAsync(content.Hash, timeout.Token);

    NotNull(loaded, "MongoDB content store did not return the inserted content.");
    Equal(content.Hash, loaded!.Hash, "MongoDB content hash changed.");
    Equal(content.Text, loaded.Text, "MongoDB content text changed.");
    Equal(content.MediaType, loaded.MediaType, "MongoDB content media type changed.");

    var repository = new RepositoryRef($"repo:mongo-smoke:{Guid.NewGuid():N}", Directory.GetCurrentDirectory());
    var staleText = "public sealed class MongoStale { }";
    var currentText = "public sealed class MongoCurrent { }";
    var staleContent = new CodeContent(
        CodeMeshHash.Sha256Hex(staleText),
        staleText,
        "text/x-csharp-fragment",
        now,
        now);
    var currentContent = new CodeContent(
        CodeMeshHash.Sha256Hex(currentText),
        currentText,
        "text/x-csharp-fragment",
        now,
        now);

    await store.UpsertContentAsync(staleContent, repository, "run:mongo-stale", now, timeout.Token);
    await store.UpsertContentAsync(currentContent, repository, "run:mongo-current", now, timeout.Token);
    await store.RemoveStaleContentAsync(repository.Id, "run:mongo-current", timeout.Token);

    IsNull(await store.GetContentAsync(staleContent.Hash, timeout.Token), "MongoDB content refresh did not remove stale content.");
    NotNull(await store.GetContentAsync(currentContent.Hash, timeout.Token), "MongoDB content refresh removed current content.");

    var incrementalRepository = new RepositoryRef($"repo:mongo-incremental:{Guid.NewGuid():N}", Directory.GetCurrentDirectory());
    var incrementalStaleText = "public sealed class MongoIncrementalStale { }";
    var incrementalCurrentText = "public sealed class MongoIncrementalCurrent { }";
    var incrementalStale = new CodeContent(
        CodeMeshHash.Sha256Hex(incrementalStaleText),
        incrementalStaleText,
        "text/x-csharp-fragment",
        now,
        now);
    var incrementalCurrent = new CodeContent(
        CodeMeshHash.Sha256Hex(incrementalCurrentText),
        incrementalCurrentText,
        "text/x-csharp-fragment",
        now,
        now);

    await store.UpsertContentAsync(incrementalStale, incrementalRepository, "run:mongo-incremental-stale", now, timeout.Token);
    await store.UpsertContentAsync(incrementalCurrent, incrementalRepository, "run:mongo-incremental-current", now, timeout.Token);

    var contentStates = await store.GetContentStatesAsync(incrementalRepository.Id, timeout.Token);
    Equal(2, contentStates.Count, "MongoDB incremental content inventory count changed.");

    await store.RemoveContentExceptAsync(
        incrementalRepository.Id,
        new HashSet<string>(StringComparer.Ordinal) { incrementalCurrent.Hash },
        timeout.Token);

    IsNull(await store.GetContentAsync(incrementalStale.Hash, timeout.Token), "MongoDB incremental cleanup did not remove stale content.");
    NotNull(await store.GetContentAsync(incrementalCurrent.Hash, timeout.Token), "MongoDB incremental cleanup removed current content.");
}

static async Task TestMongoRegistryStoreRoundTripsRepositoriesAndRuns()
{
    var unique = Guid.NewGuid().ToString("N");
    var store = new MongoRegistryStore(new MongoRegistryStoreOptions(
        Environment.GetEnvironmentVariable("CODEMESH_MONGO_URI") ?? "mongodb://127.0.0.1:27017",
        Environment.GetEnvironmentVariable("CODEMESH_MONGO_TEST_DATABASE") ?? "codemesh_tests",
        $"repositories_smoke_{unique}",
        $"ingestion_runs_smoke_{unique}",
        TimeSpan.FromSeconds(2)));

    using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
    var health = await store.CheckAsync(timeout.Token);
    if (health.State != CodeMesh.Domain.Health.ComponentState.Healthy)
    {
        var detail = health.Metadata.TryGetValue("detail", out var value) ? value : health.Message;
        throw new SkipTestException($"MongoDB is not reachable: {detail}");
    }

    var now = DateTimeOffset.UtcNow;
    var repository = new RepositoryIndexRecord(
        $"repo:mongo-registry:{unique}",
        Directory.GetCurrentDirectory(),
        null,
        "main",
        "abcdef",
        now.AddMinutes(-1),
        now,
        $"run:mongo-registry:{unique}",
        IngestionStage.Completed,
        "ok",
        7,
        11,
        5,
        7,
        new Dictionary<string, string>
        {
            ["alias"] = $"mongo_registry_{unique}",
            ["parserName"] = "registry-test"
        },
        $"mongo_registry_{unique}");
    var run = new IngestionRunIndexRecord(
        $"run:mongo-registry:{unique}",
        repository.RepositoryId,
        repository.RootPath,
        IngestionStage.Completed,
        now.AddSeconds(-10),
        now,
        "ok",
        "csharp",
        "registry-test-parser",
        "Sample.sln",
        null,
        false,
        false,
        "ollama",
        "nomic-embed-text-v2-moe:latest",
        7,
        11,
        5,
        2,
        new IngestionStats(
            7,
            1,
            6,
            11,
            2,
            9,
            5,
            0,
            5,
            2,
            5,
            SummaryCandidateCount: 4,
            WrittenSummaryCount: 2,
            SkippedSummaryCount: 1,
            FailedSummaryCount: 1),
        1,
        0,
        0,
        new Dictionary<string, string> { ["parsedAt"] = now.ToString("O") });

    await store.UpsertRepositoryAsync(repository, timeout.Token);
    await store.UpsertRunAsync(run, timeout.Token);
    await store.UpsertRepositoryAsync(repository with
    {
        LastRunId = $"run:mongo-registry-skip-embeddings:{unique}",
        LastSeenAt = now.AddSeconds(1),
        EmbeddingCount = null
    }, timeout.Token);

    var repositories = await store.ListRepositoriesAsync(cancellationToken: timeout.Token);
    Equal(1, repositories.Count, "MongoDB registry did not list repository.");
    Equal(repository.RepositoryId, repositories[0].RepositoryId, "MongoDB registry repository id changed.");
    Equal(repository.Alias ?? string.Empty, repositories[0].Alias ?? string.Empty, "MongoDB registry alias changed.");
    Equal(repository.Branch ?? string.Empty, repositories[0].Branch ?? string.Empty, "MongoDB registry branch changed.");
    Equal(repository.EmbeddingCount ?? 0, repositories[0].EmbeddingCount ?? 0, "MongoDB registry embedding count changed.");

    var loaded = await store.GetRepositoryAsync(repository.RepositoryId, timeout.Token);
    NotNull(loaded, "MongoDB registry did not load repository by id.");
    Equal($"run:mongo-registry-skip-embeddings:{unique}", loaded!.LastRunId ?? string.Empty, "MongoDB registry last run id changed.");
    Equal(7, loaded.EmbeddingCount ?? 0, "MongoDB registry skip-embeddings update erased the known embedding count.");

    var loadedByAlias = await store.GetRepositoryAsync(repository.Alias!, timeout.Token);
    NotNull(loadedByAlias, "MongoDB registry did not load repository by alias.");
    Equal(repository.RepositoryId, loadedByAlias!.RepositoryId, "MongoDB registry alias resolved to the wrong repository.");

    var runs = await store.ListRunsAsync(repository.RepositoryId, cancellationToken: timeout.Token);
    Equal(1, runs.Count, "MongoDB registry did not list run.");
    Equal(run.RunId, runs[0].RunId, "MongoDB registry run id changed.");
    Equal(run.ParserName, runs[0].ParserName, "MongoDB registry parser name changed.");
    Equal(run.Stats?.SkippedNodeCount ?? 0, runs[0].Stats?.SkippedNodeCount ?? 0, "MongoDB registry stats changed.");
    Equal(4, runs[0].Stats?.SummaryCandidateCount ?? -1, "MongoDB registry summary candidate stats changed.");
    Equal(2, runs[0].Stats?.WrittenSummaryCount ?? -1, "MongoDB registry written summary stats changed.");
    Equal(1, runs[0].Stats?.SkippedSummaryCount ?? -1, "MongoDB registry skipped summary stats changed.");
    Equal(1, runs[0].Stats?.FailedSummaryCount ?? -1, "MongoDB registry failed summary stats changed.");

    await store.DeleteRepositoryAsync(repository.RepositoryId, timeout.Token);
    IsNull(await store.GetRepositoryAsync(repository.RepositoryId, timeout.Token), "MongoDB registry did not delete repository by id.");
    IsNull(await store.GetRepositoryAsync(repository.Alias!, timeout.Token), "MongoDB registry did not delete repository alias.");
    runs = await store.ListRunsAsync(repository.RepositoryId, cancellationToken: timeout.Token);
    Equal(0, runs.Count, "MongoDB registry did not delete repository runs.");
}

static async Task TestNeo4jGraphStoreRoundTripsGraph()
{
    var uri = Environment.GetEnvironmentVariable("CODEMESH_NEO4J_URI") ?? "bolt://127.0.0.1:7687";
    var user = Environment.GetEnvironmentVariable("CODEMESH_NEO4J_USER") ?? "neo4j";
    var password = Environment.GetEnvironmentVariable("CODEMESH_NEO4J_PASSWORD") ?? "codemesh";
    var database = Environment.GetEnvironmentVariable("CODEMESH_NEO4J_DATABASE") ?? "neo4j";

    await using var store = new Neo4jGraphStore(new Neo4jGraphStoreOptions(uri, user, password, database));

    using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(15));
    var health = await store.CheckAsync(timeout.Token);
    if (health.State != CodeMesh.Domain.Health.ComponentState.Healthy)
    {
        var detail = health.Metadata.TryGetValue("detail", out var value) ? value : health.Message;
        throw new SkipTestException($"Neo4j is not reachable: {detail}");
    }

    var unique = Guid.NewGuid().ToString("N");
    var repository = new RepositoryRef($"repo:neo4j-smoke:{unique}", Directory.GetCurrentDirectory());
    var now = DateTimeOffset.UtcNow;
    var source = new CodeNode(
        "csharp:type:CodeMesh.Tests.Neo4jSmokeSource",
        "csharp:type:CodeMesh.Tests.Neo4jSmokeSource",
        CodeNodeKind.Class,
        "Neo4jSmokeSource",
        "csharp",
        "CodeMesh.Tests",
        new SourceSpan("Neo4jSmoke.cs", 1, 1, 3, 1),
        CodeMeshHash.Sha256Hex("source"),
        new Dictionary<string, string> { ["test"] = "neo4j" });
    var target = new CodeNode(
        "csharp:type:CodeMesh.Tests.Neo4jSmokeTarget",
        "csharp:type:CodeMesh.Tests.Neo4jSmokeTarget",
        CodeNodeKind.Class,
        "Neo4jSmokeTarget",
        "csharp",
        "CodeMesh.Tests",
        new SourceSpan("Neo4jSmoke.cs", 5, 1, 7, 1),
        CodeMeshHash.Sha256Hex("target"),
        new Dictionary<string, string> { ["test"] = "neo4j" });
    var relationship = new CodeRelationship(
        CodeMeshHash.StableId(source.Id, target.Id, CodeRelationshipKind.Contains.ToString()),
        source.Id,
        target.Id,
        CodeRelationshipKind.Contains,
        "contains",
        new Dictionary<string, string> { ["test"] = "neo4j" });

    await store.UpsertGraphAsync(new CodeGraphBatch(
        "batch:neo4j-smoke",
        repository,
        [source, target],
        [relationship],
        Array.Empty<CodeContent>(),
        now), timeout.Token);

    var loaded = await store.GetNodeAsync(source.Id, timeout.Token);
    NotNull(loaded, "Neo4j graph store did not return the inserted node.");
    Equal(source.Id, loaded!.Id, "Neo4j node id changed.");
    Equal(source.Kind, loaded.Kind, "Neo4j node kind changed.");
    Equal(source.Metadata["test"], loaded.Metadata["test"], "Neo4j node metadata changed.");

    var relationships = await store.GetRelationshipsAsync(source.Id, cancellationToken: timeout.Token);
    var loadedRelationship = relationships.SingleOrDefault(item => item.Id == relationship.Id);
    NotNull(loadedRelationship, "Neo4j graph store did not return the inserted relationship.");
    Equal(relationship.SourceNodeId, loadedRelationship!.SourceNodeId, "Neo4j relationship source changed.");
    Equal(relationship.TargetNodeId, loadedRelationship.TargetNodeId, "Neo4j relationship target changed.");
    Equal(relationship.Kind, loadedRelationship.Kind, "Neo4j relationship kind changed.");
    Equal(relationship.Metadata["test"], loadedRelationship.Metadata["test"], "Neo4j relationship metadata changed.");

    var collisionRepositoryA = new RepositoryRef($"repo:neo4j-collision-a:{unique}", Directory.GetCurrentDirectory());
    var collisionRepositoryB = new RepositoryRef($"repo:neo4j-collision-b:{unique}", Directory.GetCurrentDirectory());
    var sharedSourceId = $"csharp:type:CodeMesh.Tests.SharedSource{unique}";
    var sharedTargetId = $"csharp:type:CodeMesh.Tests.SharedTarget{unique}";
    var sharedRelationshipId = CodeMeshHash.StableId(sharedSourceId, sharedTargetId, CodeRelationshipKind.Contains.ToString());
    var collisionSourceA = source with
    {
        Id = sharedSourceId,
        StableKey = sharedSourceId,
        Name = $"SharedSource{unique}",
        Project = "CollisionProjectA",
        ContentHash = CodeMeshHash.Sha256Hex($"source-a-{unique}"),
        Metadata = new Dictionary<string, string> { ["repoMarker"] = "a" }
    };
    var collisionSourceB = collisionSourceA with
    {
        Project = "CollisionProjectB",
        ContentHash = CodeMeshHash.Sha256Hex($"source-b-{unique}"),
        Metadata = new Dictionary<string, string> { ["repoMarker"] = "b" }
    };
    var collisionTargetA = target with
    {
        Id = sharedTargetId,
        StableKey = sharedTargetId,
        Name = $"SharedTarget{unique}",
        Project = "CollisionProjectA",
        ContentHash = CodeMeshHash.Sha256Hex($"target-a-{unique}"),
        Metadata = new Dictionary<string, string> { ["repoMarker"] = "a" }
    };
    var collisionTargetB = collisionTargetA with
    {
        Project = "CollisionProjectB",
        ContentHash = CodeMeshHash.Sha256Hex($"target-b-{unique}"),
        Metadata = new Dictionary<string, string> { ["repoMarker"] = "b" }
    };
    var collisionRelationshipA = new CodeRelationship(
        sharedRelationshipId,
        sharedSourceId,
        sharedTargetId,
        CodeRelationshipKind.Contains,
        "contains",
        new Dictionary<string, string> { ["repoMarker"] = "a" });
    var collisionRelationshipB = collisionRelationshipA with
    {
        Metadata = new Dictionary<string, string> { ["repoMarker"] = "b" }
    };

    await store.UpsertGraphAsync(new CodeGraphBatch(
        "run:neo4j-collision-a",
        collisionRepositoryA,
        [collisionSourceA, collisionTargetA],
        [collisionRelationshipA],
        Array.Empty<CodeContent>(),
        now), timeout.Token);
    await store.UpsertGraphAsync(new CodeGraphBatch(
        "run:neo4j-collision-b",
        collisionRepositoryB,
        [collisionSourceB, collisionTargetB],
        [collisionRelationshipB],
        Array.Empty<CodeContent>(),
        now), timeout.Token);

    var loadedCollisionA = await store.GetNodeAsync(sharedSourceId, collisionRepositoryA.Id, timeout.Token);
    var loadedCollisionB = await store.GetNodeAsync(sharedSourceId, collisionRepositoryB.Id, timeout.Token);
    NotNull(loadedCollisionA, "Neo4j did not return repository A's colliding node.");
    NotNull(loadedCollisionB, "Neo4j did not return repository B's colliding node.");
    Equal("CollisionProjectA", loadedCollisionA!.Project, "Neo4j repository A node was overwritten by repository B.");
    Equal("CollisionProjectB", loadedCollisionB!.Project, "Neo4j repository B node was not stored separately.");
    Equal("a", loadedCollisionA.Metadata["repoMarker"], "Neo4j repository A node metadata changed.");
    Equal("b", loadedCollisionB.Metadata["repoMarker"], "Neo4j repository B node metadata changed.");

    var collisionRelationshipsA = await store.GetRelationshipsAsync(sharedSourceId, collisionRepositoryA.Id, cancellationToken: timeout.Token);
    var collisionRelationshipsB = await store.GetRelationshipsAsync(sharedSourceId, collisionRepositoryB.Id, cancellationToken: timeout.Token);
    var loadedCollisionRelationshipA = collisionRelationshipsA.SingleOrDefault(item => item.Id == sharedRelationshipId);
    var loadedCollisionRelationshipB = collisionRelationshipsB.SingleOrDefault(item => item.Id == sharedRelationshipId);
    NotNull(loadedCollisionRelationshipA, "Neo4j did not return repository A's colliding relationship.");
    NotNull(loadedCollisionRelationshipB, "Neo4j did not return repository B's colliding relationship.");
    Equal("a", loadedCollisionRelationshipA!.Metadata["repoMarker"], "Neo4j repository A relationship was overwritten by repository B.");
    Equal("b", loadedCollisionRelationshipB!.Metadata["repoMarker"], "Neo4j repository B relationship was not stored separately.");

    var stale = source with
    {
        Id = $"csharp:type:CodeMesh.Tests.Neo4jStale{unique}",
        StableKey = $"csharp:type:CodeMesh.Tests.Neo4jStale{unique}",
        Name = $"Neo4jStale{unique}"
    };
    var current = target with
    {
        Id = $"csharp:type:CodeMesh.Tests.Neo4jCurrent{unique}",
        StableKey = $"csharp:type:CodeMesh.Tests.Neo4jCurrent{unique}",
        Name = $"Neo4jCurrent{unique}"
    };

    await store.UpsertGraphAsync(new CodeGraphBatch(
        "run:neo4j-stale",
        repository,
        [stale],
        Array.Empty<CodeRelationship>(),
        Array.Empty<CodeContent>(),
        now), timeout.Token);
    await store.UpsertGraphAsync(new CodeGraphBatch(
        "run:neo4j-current",
        repository,
        [current],
        Array.Empty<CodeRelationship>(),
        Array.Empty<CodeContent>(),
        now), timeout.Token);
    await store.RemoveStaleGraphAsync(repository.Id, "run:neo4j-current", timeout.Token);

    IsNull(await store.GetNodeAsync(stale.Id, timeout.Token), "Neo4j graph refresh did not remove stale node.");
    NotNull(await store.GetNodeAsync(current.Id, timeout.Token), "Neo4j graph refresh removed current node.");

    var incrementalRepository = new RepositoryRef($"repo:neo4j-incremental:{unique}", Directory.GetCurrentDirectory());
    var incrementalStale = source with
    {
        Id = $"csharp:type:CodeMesh.Tests.Neo4jIncrementalStale{unique}",
        StableKey = $"csharp:type:CodeMesh.Tests.Neo4jIncrementalStale{unique}",
        Name = $"Neo4jIncrementalStale{unique}"
    };
    var incrementalCurrent = target with
    {
        Id = $"csharp:type:CodeMesh.Tests.Neo4jIncrementalCurrent{unique}",
        StableKey = $"csharp:type:CodeMesh.Tests.Neo4jIncrementalCurrent{unique}",
        Name = $"Neo4jIncrementalCurrent{unique}"
    };
    var incrementalRelationship = new CodeRelationship(
        CodeMeshHash.StableId(incrementalStale.Id, incrementalCurrent.Id, CodeRelationshipKind.Contains.ToString()),
        incrementalStale.Id,
        incrementalCurrent.Id,
        CodeRelationshipKind.Contains,
        "contains",
        new Dictionary<string, string> { ["test"] = "neo4j-incremental" });

    await store.UpsertGraphAsync(new CodeGraphBatch(
        "run:neo4j-incremental",
        incrementalRepository,
        [incrementalStale, incrementalCurrent],
        [incrementalRelationship],
        Array.Empty<CodeContent>(),
        now), timeout.Token);

    var nodeStates = await store.GetNodeStatesAsync(incrementalRepository.Id, timeout.Token);
    var relationshipStates = await store.GetRelationshipStatesAsync(incrementalRepository.Id, timeout.Token);
    Equal(2, nodeStates.Count, "Neo4j incremental node inventory count changed.");
    Equal(1, relationshipStates.Count, "Neo4j incremental relationship inventory count changed.");

    await store.RemoveGraphExceptAsync(
        incrementalRepository.Id,
        new HashSet<string>(StringComparer.Ordinal) { incrementalCurrent.Id },
        new HashSet<string>(StringComparer.Ordinal),
        timeout.Token);

    IsNull(await store.GetNodeAsync(incrementalStale.Id, timeout.Token), "Neo4j incremental cleanup did not remove stale node.");
    NotNull(await store.GetNodeAsync(incrementalCurrent.Id, timeout.Token), "Neo4j incremental cleanup removed current node.");
}

static async Task TestQdrantVectorStoreRoundTripsEmbeddings()
{
    var url = Environment.GetEnvironmentVariable("CODEMESH_QDRANT_URL") ?? "http://127.0.0.1:6333";
    var configuredCollection = Environment.GetEnvironmentVariable("CODEMESH_QDRANT_TEST_COLLECTION");
    var collection = string.IsNullOrWhiteSpace(configuredCollection)
        ? $"codemesh_tests_vectors_{Guid.NewGuid():N}"
        : configuredCollection;

    try
    {
        using var store = new QdrantVectorStore(new QdrantVectorStoreOptions(url, collection, Timeout: TimeSpan.FromSeconds(2)));

        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(10));
        var health = await store.CheckAsync(timeout.Token);
        if (health.State != CodeMesh.Domain.Health.ComponentState.Healthy)
        {
            var detail = health.Metadata.TryGetValue("detail", out var value) ? value : health.Message;
            throw new SkipTestException($"Qdrant is not reachable: {detail}");
        }

        var unique = Guid.NewGuid().ToString("N");
        var first = new EmbeddingRecord(
            $"embedding:qdrant:{unique}:alpha",
            $"node:qdrant:{unique}:alpha",
            $"hash:qdrant:{unique}:alpha",
            "test",
            "unit",
            3,
            [1.0f, 0.0f, 0.0f],
            new Dictionary<string, string>
            {
                ["preview"] = "alpha vector",
                ["smokeTest"] = unique
            });
        var second = new EmbeddingRecord(
            $"embedding:qdrant:{unique}:beta",
            $"node:qdrant:{unique}:beta",
            $"hash:qdrant:{unique}:beta",
            "test",
            "unit",
            3,
            [0.0f, 1.0f, 0.0f],
            new Dictionary<string, string>
            {
                ["preview"] = "beta vector",
                ["smokeTest"] = unique
            });

        await store.UpsertEmbeddingsAsync([first, second], timeout.Token);

        var matches = await store.SearchAsync(
            [1.0f, 0.0f, 0.0f],
            2,
            new Dictionary<string, string> { ["smokeTest"] = unique },
            timeout.Token);

        if (matches.Count == 0)
        {
            throw new InvalidOperationException("Qdrant vector store returned no matches.");
        }

        Equal(first.NodeId, matches[0].NodeId, "Qdrant nearest match node id changed.");
        Equal(first.ContentHash, matches[0].ContentHash, "Qdrant nearest match content hash changed.");
        Equal("alpha vector", matches[0].Preview ?? string.Empty, "Qdrant nearest match preview changed.");
        Equal(unique, matches[0].Metadata["smokeTest"], "Qdrant nearest match metadata changed.");

        var collisionRepositoryA = $"repo:qdrant-collision-a:{unique}";
        var collisionRepositoryB = $"repo:qdrant-collision-b:{unique}";
        var sharedEmbeddingId = $"embedding:qdrant:{unique}:shared";
        var sharedNodeId = $"node:qdrant:{unique}:shared";
        var collisionA = new EmbeddingRecord(
            sharedEmbeddingId,
            sharedNodeId,
            $"hash:qdrant:{unique}:collision-a",
            "test",
            "unit",
            3,
            [0.5f, 0.5f, 0.0f],
            new Dictionary<string, string>
            {
                ["repositoryId"] = collisionRepositoryA,
                ["preview"] = "collision vector a"
            });
        var collisionB = new EmbeddingRecord(
            sharedEmbeddingId,
            sharedNodeId,
            $"hash:qdrant:{unique}:collision-b",
            "test",
            "unit",
            3,
            [0.5f, 0.5f, 0.0f],
            new Dictionary<string, string>
            {
                ["repositoryId"] = collisionRepositoryB,
                ["preview"] = "collision vector b"
            });

        await store.UpsertEmbeddingsAsync([collisionA, collisionB], timeout.Token);

        var collisionMatchesA = await store.SearchAsync(
            [0.5f, 0.5f, 0.0f],
            1,
            new Dictionary<string, string> { ["repositoryId"] = collisionRepositoryA },
            timeout.Token);
        var collisionMatchesB = await store.SearchAsync(
            [0.5f, 0.5f, 0.0f],
            1,
            new Dictionary<string, string> { ["repositoryId"] = collisionRepositoryB },
            timeout.Token);

        Equal(1, collisionMatchesA.Count, "Qdrant did not retain repository A's colliding embedding.");
        Equal(1, collisionMatchesB.Count, "Qdrant did not retain repository B's colliding embedding.");
        Equal(collisionA.ContentHash, collisionMatchesA[0].ContentHash, "Qdrant repository A embedding was overwritten by repository B.");
        Equal(collisionB.ContentHash, collisionMatchesB[0].ContentHash, "Qdrant repository B embedding was not stored separately.");
        Equal("collision vector a", collisionMatchesA[0].Preview ?? string.Empty, "Qdrant repository A preview changed.");
        Equal("collision vector b", collisionMatchesB[0].Preview ?? string.Empty, "Qdrant repository B preview changed.");

        var repositoryId = $"repo:qdrant:{unique}";
        var stale = new EmbeddingRecord(
            $"embedding:qdrant:{unique}:stale",
            $"node:qdrant:{unique}:stale",
            $"hash:qdrant:{unique}:stale",
            "test",
            "unit",
            3,
            [0.0f, 0.0f, 1.0f],
            new Dictionary<string, string>
            {
                ["repositoryId"] = repositoryId,
                ["ingestionRunId"] = "run:qdrant-stale",
                ["preview"] = "stale vector"
            });
        var current = new EmbeddingRecord(
            $"embedding:qdrant:{unique}:current",
            $"node:qdrant:{unique}:current",
            $"hash:qdrant:{unique}:current",
            "test",
            "unit",
            3,
            [0.0f, 0.0f, 1.0f],
            new Dictionary<string, string>
            {
                ["repositoryId"] = repositoryId,
                ["ingestionRunId"] = "run:qdrant-current",
                ["preview"] = "current vector"
            });

        await store.UpsertEmbeddingsAsync([stale, current], timeout.Token);
        await store.RemoveStaleEmbeddingsAsync(repositoryId, "run:qdrant-current", timeout.Token);

        var refreshMatches = await store.SearchAsync(
            [0.0f, 0.0f, 1.0f],
            10,
            new Dictionary<string, string> { ["repositoryId"] = repositoryId },
            timeout.Token);
        if (refreshMatches.Any(match => string.Equals(match.NodeId, stale.NodeId, StringComparison.Ordinal)))
        {
            throw new InvalidOperationException("Qdrant vector refresh did not remove stale embedding.");
        }

        if (!refreshMatches.Any(match => string.Equals(match.NodeId, current.NodeId, StringComparison.Ordinal)))
        {
            throw new InvalidOperationException("Qdrant vector refresh removed current embedding.");
        }

        var incrementalRepositoryId = $"repo:qdrant-incremental:{unique}";
        var incrementalStale = new EmbeddingRecord(
            $"embedding:qdrant:{unique}:incremental-stale",
            $"node:qdrant:{unique}:incremental-stale",
            $"hash:qdrant:{unique}:incremental-stale",
            "test",
            "unit",
            3,
            [0.0f, 0.0f, 1.0f],
            new Dictionary<string, string>
            {
                ["repositoryId"] = incrementalRepositoryId,
                ["preview"] = "incremental stale vector"
            });
        var incrementalCurrent = new EmbeddingRecord(
            $"embedding:qdrant:{unique}:incremental-current",
            $"node:qdrant:{unique}:incremental-current",
            $"hash:qdrant:{unique}:incremental-current",
            "test",
            "unit",
            3,
            [0.0f, 0.0f, 1.0f],
            new Dictionary<string, string>
            {
                ["repositoryId"] = incrementalRepositoryId,
                ["preview"] = "incremental current vector"
            });

        await store.UpsertEmbeddingsAsync([incrementalStale, incrementalCurrent], timeout.Token);

        var embeddingStates = await store.GetEmbeddingStatesAsync(incrementalRepositoryId, timeout.Token);
        Equal(2, embeddingStates.Count, "Qdrant incremental embedding inventory count changed.");

        await store.RemoveEmbeddingsExceptAsync(
            incrementalRepositoryId,
            new HashSet<string>(StringComparer.Ordinal) { incrementalCurrent.Id },
            timeout.Token);

        var incrementalMatches = await store.SearchAsync(
            [0.0f, 0.0f, 1.0f],
            10,
            new Dictionary<string, string> { ["repositoryId"] = incrementalRepositoryId },
            timeout.Token);
        if (incrementalMatches.Any(match => string.Equals(match.NodeId, incrementalStale.NodeId, StringComparison.Ordinal)))
        {
            throw new InvalidOperationException("Qdrant incremental cleanup did not remove stale embedding.");
        }

        if (!incrementalMatches.Any(match => string.Equals(match.NodeId, incrementalCurrent.NodeId, StringComparison.Ordinal)))
        {
            throw new InvalidOperationException("Qdrant incremental cleanup removed current embedding.");
        }
    }
    finally
    {
        if (string.IsNullOrWhiteSpace(configuredCollection))
        {
            await DeleteQdrantCollectionAsync(url, collection);
        }
    }
}

static async Task TestCSharpParserEmitsRoslynSymbols()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-parser-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        await File.WriteAllTextAsync(
            Path.Combine(root, "Demo.cs"),
            """
            namespace Sample;

            public interface IWorker
            {
                Demo Create(Demo input, int count);
            }

            public abstract class BaseWorker
            {
                public abstract Demo Create(Demo input, int count);
            }

            public sealed class DemoWorker : BaseWorker, IWorker
            {
                public override Demo Create(Demo input, int count) => input;
            }

            public sealed class Demo
            {
                public int Count { get; init; }
            }
            """);

        var parser = new CSharpParseService();
        var result = await parser.ParseAsync(new ParseRequest(
            root,
            null,
            null,
            "csharp",
            new Dictionary<string, string>()));

        var errors = result.Diagnostics
            .Where(diagnostic => string.Equals(diagnostic.Severity, "error", StringComparison.OrdinalIgnoreCase))
            .Select(diagnostic => diagnostic.Message)
            .ToArray();

        if (errors.Length > 0)
        {
            throw new InvalidOperationException($"Parser returned errors: {string.Join("; ", errors)}");
        }

        HasNode(result, CodeNodeKind.Namespace, "Sample");
        HasNode(result, CodeNodeKind.Interface, "IWorker");
        HasNode(result, CodeNodeKind.Class, "DemoWorker");
        HasNode(result, CodeNodeKind.Method, "Create");
        HasNode(result, CodeNodeKind.Parameter, "count");
        HasNode(result, CodeNodeKind.Property, "Count");
        HasNode(result, CodeNodeKind.Declaration, "DemoWorker");
        HasNodeId(result, "csharp:file:Demo.cs");
        HasNodeId(result, "csharp:namespace:Sample");
        HasNodeId(result, "csharp:type:Sample.DemoWorker");
        HasNodeId(result, "csharp:decl:csharp:type:Sample.DemoWorker:Demo.cs:13:1");
        HasNodeId(result, "csharp:method:Sample.DemoWorker.Create(Sample.Demo,System.Int32)");
        HasNodeId(result, "csharp:param:Sample.DemoWorker.Create(Sample.Demo,System.Int32):0:input");
        HasNodeId(result, "csharp:property:Sample.Demo.Count");

        HasRelationship(result, CodeRelationshipKind.Contains);
        HasRelationship(result, CodeRelationshipKind.Inherits);
        HasRelationship(result, CodeRelationshipKind.Implements);
        HasRelationship(result, CodeRelationshipKind.Returns);
        HasRelationship(result, CodeRelationshipKind.Overrides);
        HasRelationship(result, CodeRelationshipKind.UsesType);
        HasRelationshipBetween(
            result,
            "csharp:decl:csharp:type:Sample.DemoWorker:Demo.cs:13:1",
            "csharp:type:Sample.DemoWorker",
            CodeRelationshipKind.Defines);
        HasRelationshipBetween(
            result,
            "csharp:type:Sample.DemoWorker",
            "csharp:method:Sample.DemoWorker.Create(Sample.Demo,System.Int32)",
            CodeRelationshipKind.Contains);
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestCSharpParserEmitsInvocationAndMemberAccessRelationships()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-parser-calls-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        await File.WriteAllTextAsync(
            Path.Combine(root, "Calls.cs"),
            """
            namespace Sample;

            public sealed class Worker
            {
                private int _count;

                public int Count
                {
                    get => _count;
                    set => _count = value;
                }

                public void Run()
                {
                    Count = Helper();
                }

                private int Helper()
                {
                    return Count;
                }
            }
            """);

        var parser = new CSharpParseService();
        var result = await parser.ParseAsync(new ParseRequest(
            root,
            null,
            null,
            "csharp",
            new Dictionary<string, string>()));

        var errors = result.Diagnostics
            .Where(diagnostic => string.Equals(diagnostic.Severity, "error", StringComparison.OrdinalIgnoreCase))
            .Select(diagnostic => diagnostic.Message)
            .ToArray();

        if (errors.Length > 0)
        {
            throw new InvalidOperationException($"Parser returned errors: {string.Join("; ", errors)}");
        }

        const string run = "csharp:method:Sample.Worker.Run()";
        const string helper = "csharp:method:Sample.Worker.Helper()";
        const string count = "csharp:property:Sample.Worker.Count";
        const string field = "csharp:field:Sample.Worker._count";

        HasRelationshipBetween(result, run, helper, CodeRelationshipKind.Invokes);
        HasRelationshipBetween(result, run, count, CodeRelationshipKind.Writes);
        HasRelationshipBetween(result, helper, count, CodeRelationshipKind.Reads);
        HasRelationshipBetween(result, count, field, CodeRelationshipKind.Reads);
        HasRelationshipBetween(result, count, field, CodeRelationshipKind.Writes);
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestCSharpParserSeparatesPartialDeclarations()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-parser-partial-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        await File.WriteAllTextAsync(
            Path.Combine(root, "Customer.cs"),
            """
            namespace Sample;

            public sealed partial class Customer
            {
                public string Name { get; set; } = "";
            }
            """);

        await File.WriteAllTextAsync(
            Path.Combine(root, "Customer.Validation.cs"),
            """
            namespace Sample;

            public sealed partial class Customer
            {
                public bool IsValid() => !string.IsNullOrWhiteSpace(Name);
            }
            """);

        var parser = new CSharpParseService();
        var result = await parser.ParseAsync(new ParseRequest(
            root,
            null,
            null,
            "csharp",
            new Dictionary<string, string>()));

        Equal(1, result.Nodes.Count(node => string.Equals(node.Id, "csharp:type:Sample.Customer", StringComparison.Ordinal)), "Expected one logical Customer type node.");
        Equal(2, result.Nodes.Count(node =>
            node.Kind == CodeNodeKind.Declaration &&
            node.Metadata.TryGetValue("symbolId", out var symbolId) &&
            string.Equals(symbolId, "csharp:type:Sample.Customer", StringComparison.Ordinal)), "Expected two Customer declaration nodes.");

        HasRelationshipBetween(
            result,
            "csharp:decl:csharp:type:Sample.Customer:Customer.cs:3:1",
            "csharp:type:Sample.Customer",
            CodeRelationshipKind.Defines);
        HasRelationshipBetween(
            result,
            "csharp:decl:csharp:type:Sample.Customer:Customer.Validation.cs:3:1",
            "csharp:type:Sample.Customer",
            CodeRelationshipKind.Defines);
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestCSharpParserHonorsProjectCompileItems()
{
    var root = Path.Combine(Path.GetTempPath(), $"codemesh-parser-project-test-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);

    try
    {
        var projectPath = Path.Combine(root, "ProjectLoading.csproj");
        await File.WriteAllTextAsync(
            projectPath,
            """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup>
                <TargetFramework>net10.0</TargetFramework>
                <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
                <ImplicitUsings>disable</ImplicitUsings>
                <Nullable>enable</Nullable>
              </PropertyGroup>
              <ItemGroup>
                <Compile Include="Included.cs" />
              </ItemGroup>
            </Project>
            """);

        await File.WriteAllTextAsync(
            Path.Combine(root, "Included.cs"),
            """
            namespace Sample;

            public sealed class Included
            {
            }
            """);

        await File.WriteAllTextAsync(
            Path.Combine(root, "Excluded.cs"),
            """
            namespace Sample;

            public sealed class Excluded
            {
            }
            """);

        var parser = new CSharpParseService();
        var result = await parser.ParseAsync(new ParseRequest(
            root,
            null,
            projectPath,
            "csharp",
            new Dictionary<string, string>()));

        var errors = result.Diagnostics
            .Where(diagnostic => string.Equals(diagnostic.Severity, "error", StringComparison.OrdinalIgnoreCase))
            .Select(diagnostic => diagnostic.Message)
            .ToArray();

        if (errors.Length > 0)
        {
            throw new InvalidOperationException($"Parser returned errors: {string.Join("; ", errors)}");
        }

        HasNodeId(result, "csharp:file:Included.cs");
        HasNodeId(result, "csharp:type:Sample.Included");
        HasNoNodeId(result, "csharp:file:Excluded.cs", result);
        HasNoNodeId(result, "csharp:type:Sample.Excluded", result);
    }
    finally
    {
        Directory.Delete(root, recursive: true);
    }
}

static async Task TestYoutubeDownloaderSampleParser()
{
    var sampleRoot = Environment.GetEnvironmentVariable("CODEMESH_SAMPLE_CSHARP_ROOT")
        ?? @"D:\source\repos\YoutubeDownloader";
    var solutionPath = Environment.GetEnvironmentVariable("CODEMESH_SAMPLE_CSHARP_SOLUTION")
        ?? Path.Combine(sampleRoot, "YoutubeDownloader.slnx");

    if (!Directory.Exists(sampleRoot))
    {
        throw new SkipTestException($"Sample root not found: {sampleRoot}");
    }

    var parser = new CSharpParseService();
    var result = await parser.ParseAsync(new ParseRequest(
        sampleRoot,
        File.Exists(solutionPath) ? solutionPath : null,
        null,
        "csharp",
        new Dictionary<string, string>()));

    var errors = result.Diagnostics
        .Where(diagnostic => string.Equals(diagnostic.Severity, "error", StringComparison.OrdinalIgnoreCase))
        .Select(diagnostic => diagnostic.Message)
        .ToArray();

    if (errors.Length > 0)
    {
        throw new InvalidOperationException($"Parser returned errors: {string.Join("; ", errors)}");
    }

    if (result.Nodes.Count == 0)
    {
        throw new InvalidOperationException("Parser returned no nodes for the YoutubeDownloader sample.");
    }

    Equal(result.Nodes.Count, result.Contents.Count, "File-level parser should emit one content item per node.");

    var hasExpectedFile = result.Nodes.Any(node =>
        string.Equals(
            node.Span.FilePath.Replace('\\', '/'),
            "YoutubeDownloader.Core/Downloading/VideoDownloader.cs",
            StringComparison.OrdinalIgnoreCase));

    if (!hasExpectedFile)
    {
        throw new InvalidOperationException("Parser did not include the expected VideoDownloader.cs sample file.");
    }
}

static void HasNode(ParseResult result, CodeNodeKind kind, string name)
{
    if (!result.Nodes.Any(node => node.Kind == kind && string.Equals(node.Name, name, StringComparison.Ordinal)))
    {
        throw new InvalidOperationException($"Expected parser to emit {kind} node named {name}.");
    }
}

static void HasNodeId(ParseResult result, string nodeId)
{
    if (!result.Nodes.Any(node => string.Equals(node.Id, nodeId, StringComparison.Ordinal)))
    {
        throw new InvalidOperationException($"Expected parser to emit node id {nodeId}.");
    }
}

static void HasNoNodeId(ParseResult result, string nodeId, ParseResult? diagnosticSource = null)
{
    if (result.Nodes.Any(node => string.Equals(node.Id, nodeId, StringComparison.Ordinal)))
    {
        var diagnostics = diagnosticSource is null
            ? string.Empty
            : $" Diagnostics: {string.Join(" | ", diagnosticSource.Diagnostics.Select(diagnostic => $"{diagnostic.Code}:{diagnostic.Severity}:{diagnostic.Message}"))}";
        throw new InvalidOperationException($"Expected parser not to emit node id {nodeId}.{diagnostics}");
    }
}

static void HasRelationship(ParseResult result, CodeRelationshipKind kind)
{
    if (!result.Relationships.Any(relationship => relationship.Kind == kind))
    {
        throw new InvalidOperationException($"Expected parser to emit {kind} relationship.");
    }
}

static void HasRelationshipBetween(ParseResult result, string sourceNodeId, string targetNodeId, CodeRelationshipKind kind)
{
    if (!result.Relationships.Any(relationship =>
        relationship.Kind == kind &&
        string.Equals(relationship.SourceNodeId, sourceNodeId, StringComparison.Ordinal) &&
        string.Equals(relationship.TargetNodeId, targetNodeId, StringComparison.Ordinal)))
    {
        throw new InvalidOperationException($"Expected parser to emit {kind} relationship from {sourceNodeId} to {targetNodeId}.");
    }
}

static void Equal<T>(T expected, T actual, string message)
{
    if (!EqualityComparer<T>.Default.Equals(expected, actual))
    {
        throw new InvalidOperationException($"{message} Expected {expected}, got {actual}.");
    }
}

static void NotNull<T>(T? value, string message)
{
    if (value is null)
    {
        throw new InvalidOperationException(message);
    }
}

static void IsNull<T>(T? value, string message)
{
    if (value is not null)
    {
        throw new InvalidOperationException(message);
    }
}

static async Task DeleteQdrantCollectionAsync(string url, string collection)
{
    try
    {
        var baseAddress = url.EndsWith("/", StringComparison.Ordinal) ? url : $"{url}/";
        using var client = new HttpClient
        {
            BaseAddress = new Uri(baseAddress, UriKind.Absolute),
            Timeout = TimeSpan.FromSeconds(2)
        };

        using var response = await client.DeleteAsync($"collections/{Uri.EscapeDataString(collection)}");
    }
    catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException)
    {
    }
}

sealed class SkipTestException(string message) : Exception(message);

sealed class SlowHttpServer : IAsyncDisposable
{
    private readonly TcpListener _listener;
    private readonly CancellationTokenSource _cancellation = new();
    private readonly Task _serverTask;
    private readonly TimeSpan _delay;
    private readonly string _responseBody;
    private int _failuresBeforeSuccess;
    private int _requestCount;

    public SlowHttpServer(
        TimeSpan delay,
        int failuresBeforeSuccess = 0,
        string responseBody = """{"models":[{"name":"test-embed"}]}""")
    {
        _delay = delay;
        _failuresBeforeSuccess = failuresBeforeSuccess;
        _responseBody = responseBody;
        _listener = new TcpListener(IPAddress.Loopback, 0);
        _listener.Start();

        var endpoint = (IPEndPoint)_listener.LocalEndpoint;
        BaseUrl = $"http://127.0.0.1:{endpoint.Port}";
        _serverTask = Task.Run(ServeAsync);
    }

    public string BaseUrl { get; }
    public int RequestCount => Volatile.Read(ref _requestCount);

    public async ValueTask DisposeAsync()
    {
        await _cancellation.CancelAsync();
        _listener.Stop();

        try
        {
            await _serverTask;
        }
        catch (OperationCanceledException)
        {
        }
        catch (SocketException)
        {
        }

        _cancellation.Dispose();
    }

    private async Task ServeAsync()
    {
        while (!_cancellation.IsCancellationRequested)
        {
            using var client = await _listener
                .AcceptTcpClientAsync(_cancellation.Token)
                .ConfigureAwait(false);

            await HandleClientAsync(client, _cancellation.Token)
                .ConfigureAwait(false);
        }
    }

    private async Task HandleClientAsync(TcpClient client, CancellationToken cancellationToken)
    {
        await using var stream = client.GetStream();
        var buffer = new byte[1024];

        while (!cancellationToken.IsCancellationRequested)
        {
            var bytesRead = await stream.ReadAsync(buffer, cancellationToken).ConfigureAwait(false);
            if (bytesRead == 0)
            {
                return;
            }

            var request = Encoding.ASCII.GetString(buffer, 0, bytesRead);
            if (request.Contains("\r\n\r\n", StringComparison.Ordinal))
            {
                break;
            }
        }

        Interlocked.Increment(ref _requestCount);
        if (Interlocked.CompareExchange(ref _failuresBeforeSuccess, 0, 0) > 0)
        {
            Interlocked.Decrement(ref _failuresBeforeSuccess);
            return;
        }

        await Task.Delay(_delay, cancellationToken).ConfigureAwait(false);

        var response = Encoding.ASCII.GetBytes(
            $"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {_responseBody.Length}\r\nConnection: close\r\n\r\n{_responseBody}");
        await stream.WriteAsync(response, cancellationToken).ConfigureAwait(false);
    }
}

sealed class FakeParserClient : IParserClient
{
    private const string Text = "public sealed class Demo { }";
    public static readonly string ContentHash = CodeMeshHash.Sha256Hex(Text);
    public static readonly string NodeId = CodeMeshHash.StableId("fake", "Demo.cs", ContentHash);

    public Task<ParserCapability> GetCapabilityAsync(CancellationToken cancellationToken = default)
    {
        return Task.FromResult(new ParserCapability(
            "fake-parser",
            "csharp",
            "test",
            [".cs"],
            ["repositoryRoot"]));
    }

    public Task<ParseResult> ParseAsync(ParseRequest request, CancellationToken cancellationToken = default)
    {
        var now = DateTimeOffset.UtcNow;
        var node = new CodeNode(
            NodeId,
            "Demo:Demo.cs",
            CodeNodeKind.File,
            "Demo.cs",
            "csharp",
            "Demo",
            new SourceSpan("Demo.cs", 1, 1, 1, 1),
            ContentHash,
            new Dictionary<string, string>());

        var content = new CodeContent(
            ContentHash,
            Text,
            "text/x-csharp",
            now,
            now);

        return Task.FromResult(new ParseResult(
            "fake-parser",
            "csharp",
            [node],
            Array.Empty<CodeRelationship>(),
            [content],
            Array.Empty<ParserDiagnostic>(),
            now));
    }
}

sealed class RefreshParserClient(string typeName) : IParserClient
{
    public string TypeName { get; set; } = typeName;

    public static string NodeIdFor(string typeName) => $"csharp:type:Sample.{typeName}";

    public static string ContentHashFor(string typeName) => CodeMeshHash.Sha256Hex(TextFor(typeName));

    public Task<ParserCapability> GetCapabilityAsync(CancellationToken cancellationToken = default)
    {
        return Task.FromResult(new ParserCapability(
            "refresh-parser",
            "csharp",
            "test",
            [".cs"],
            ["repositoryRoot"]));
    }

    public Task<ParseResult> ParseAsync(ParseRequest request, CancellationToken cancellationToken = default)
    {
        var now = DateTimeOffset.UtcNow;
        var text = TextFor(TypeName);
        var hash = CodeMeshHash.Sha256Hex(text);
        var node = new CodeNode(
            NodeIdFor(TypeName),
            NodeIdFor(TypeName),
            CodeNodeKind.Class,
            TypeName,
            "csharp",
            "Sample",
            new SourceSpan($"{TypeName}.cs", 1, 1, 1, text.Length),
            hash,
            new Dictionary<string, string>());
        var content = new CodeContent(
            hash,
            text,
            "text/x-csharp-fragment",
            now,
            now);

        return Task.FromResult(new ParseResult(
            "refresh-parser",
            "csharp",
            [node],
            Array.Empty<CodeRelationship>(),
            [content],
            Array.Empty<ParserDiagnostic>(),
            now));
    }

    private static string TextFor(string typeName) => $"namespace Sample; public sealed class {typeName} {{ }}";
}

sealed class DeterministicEmbeddingProvider : IEmbeddingProvider
{
    public string Provider => "test";

    public string Model => "deterministic";

    public Task<IReadOnlyList<EmbeddingRecord>> EmbedAsync(
        IReadOnlyList<CodeNode> nodes,
        IReadOnlyDictionary<string, CodeContent> contentByHash,
        CancellationToken cancellationToken = default)
    {
        IReadOnlyList<EmbeddingRecord> embeddings = nodes
            .Select(node => new EmbeddingRecord(
                CodeMeshHash.StableId("embedding", node.Id, node.ContentHash),
                node.Id,
                node.ContentHash,
                Provider,
                Model,
                2,
                [1.0f, 0.0f],
                new Dictionary<string, string>
                {
                    ["preview"] = node.Name
                }))
            .ToArray();

        return Task.FromResult(embeddings);
    }
}

sealed class CountingEmbeddingProvider : IEmbeddingProvider
{
    public int EmbeddedNodeCount { get; private set; }

    public string Provider => "test";

    public string Model => "counting";

    public Task<IReadOnlyList<EmbeddingRecord>> EmbedAsync(
        IReadOnlyList<CodeNode> nodes,
        IReadOnlyDictionary<string, CodeContent> contentByHash,
        CancellationToken cancellationToken = default)
    {
        EmbeddedNodeCount += nodes.Count;

        IReadOnlyList<EmbeddingRecord> embeddings = nodes
            .Select(node => new EmbeddingRecord(
                CodeMeshHash.StableId("embedding", Provider, Model, node.Id, node.ContentHash),
                node.Id,
                node.ContentHash,
                Provider,
                Model,
                2,
                [1.0f, 0.0f],
                new Dictionary<string, string>
                {
                    ["preview"] = node.Name
                }))
            .ToArray();

        return Task.FromResult(embeddings);
    }
}

sealed class CountingSummaryProvider : ICodeSummaryProvider
{
    public int SummarizedNodeCount { get; private set; }

    public string Provider => "test";

    public string Model => "summary-counting";

    public Task<CodeSummaryResult> SummarizeAsync(
        CodeSummaryRequest request,
        CancellationToken cancellationToken = default)
    {
        SummarizedNodeCount++;
        return Task.FromResult(new CodeSummaryResult(
            $"Summarizes {request.Node.Kind} {request.Node.Name}.",
            [request.Node.Kind.ToString().ToLowerInvariant()],
            "high"));
    }
}

sealed class FakeOllamaEmbeddingHandler : HttpMessageHandler
{
    public int RequestCount { get; private set; }
    public string LastRequestBody { get; private set; } = string.Empty;

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        RequestCount++;
        LastRequestBody = request.Content is null
            ? string.Empty
            : await request.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);

        if (request.RequestUri?.AbsolutePath != "/api/embed")
        {
            return new HttpResponseMessage(System.Net.HttpStatusCode.NotFound);
        }

        var response = new HttpResponseMessage(System.Net.HttpStatusCode.OK)
        {
            Content = new StringContent(
                """
                {
                  "model": "test-embed",
                  "embeddings": [[0.25, 0.5, 0.75]]
                }
                """,
                System.Text.Encoding.UTF8,
                "application/json")
        };

        return response;
    }
}

sealed class FakeLmStudioEmbeddingHandler : HttpMessageHandler
{
    public int RequestCount { get; private set; }
    public string LastRequestBody { get; private set; } = string.Empty;

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        RequestCount++;
        LastRequestBody = request.Content is null
            ? string.Empty
            : await request.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);

        if (request.RequestUri?.AbsolutePath != "/v1/embeddings")
        {
            return new HttpResponseMessage(System.Net.HttpStatusCode.NotFound);
        }

        var response = new HttpResponseMessage(System.Net.HttpStatusCode.OK)
        {
            Content = new StringContent(
                """
                {
                  "object": "list",
                  "model": "test-embed",
                  "data": [
                    {
                      "object": "embedding",
                      "index": 0,
                      "embedding": [0.125, 0.25, 0.5]
                    }
                  ]
                }
                """,
                System.Text.Encoding.UTF8,
                "application/json")
        };

        return response;
    }
}

sealed class FakeLmStudioSummaryHandler : HttpMessageHandler
{
    public int RequestCount { get; private set; }
    public string LastRequestBody { get; private set; } = string.Empty;

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        RequestCount++;
        LastRequestBody = request.Content is null
            ? string.Empty
            : await request.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);

        if (request.RequestUri?.AbsolutePath != "/v1/chat/completions")
        {
            return new HttpResponseMessage(System.Net.HttpStatusCode.NotFound);
        }

        var response = new HttpResponseMessage(System.Net.HttpStatusCode.OK)
        {
            Content = new StringContent(
                """
                {
                  "id": "chatcmpl-test",
                  "object": "chat.completion",
                  "model": "test-summary",
                  "choices": [
                    {
                      "index": 0,
                      "message": {
                        "role": "assistant",
                        "content": "```json\n{\"summary\":\"Trims a URL and converts it to lowercase.\",\"tags\":[\"normalization\",\"url\"],\"confidence\":0.98}\n```"
                      },
                      "finish_reason": "stop"
                    }
                  ]
                }
                """,
                System.Text.Encoding.UTF8,
                "application/json")
        };

        return response;
    }
}

sealed class FakeAgentAccessHandler : HttpMessageHandler
{
    public List<(string Method, string Path, string Body)> Requests { get; } = [];

    public bool FailNextRequest { get; set; }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        var path = request.RequestUri?.PathAndQuery.TrimStart('/') ?? string.Empty;
        var body = request.Content is null
            ? string.Empty
            : await request.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);

        Requests.Add((request.Method.Method, path, body));

        if (FailNextRequest)
        {
            FailNextRequest = false;
            return JsonResponse(HttpStatusCode.ServiceUnavailable, """{"detail":"offline"}""");
        }

        var payload = request.Method == HttpMethod.Delete
            ? DeletePayload(path)
            : path switch
        {
            "health" or "status" =>
                """
                {
                  "service": "codemesh-agent-access",
                  "status": "healthy",
                  "checked_at": "2026-06-06T10:00:00Z",
                  "components": {
                    "neo4j": {"status": "healthy"},
                    "mongodb": {"status": "healthy"},
                    "qdrant": {"status": "healthy"},
                    "model_provider": {
                      "provider": "lmstudio",
                      "embedding_model": "text-embedding-nomic-embed-text-v2-moe",
                      "status": "healthy"
                    }
                  }
                }
                """,
            "context/search" =>
                """
                {
                  "query": {"query": "DownloadAsync", "repository_id": "repo:test"},
                  "hits": [
                    {
                      "node_id": "node:download",
                      "stable_key": "stable:download",
                      "kind": "Method",
                      "file_path": "Downloader.cs",
                      "start_line": 10,
                      "end_line": 20,
                      "score": 0.91
                    }
                  ],
                  "diagnostics": {
                    "mode": "hybrid",
                    "embedding_attempted": true,
                    "embedding_source": "model_provider",
                    "model_provider": "lmstudio",
                    "vector_available": true,
                    "vector_hit_count": 1,
                    "lexical_hit_count": 1,
                    "summary_hit_count": 0,
                    "vector_candidate_count": 1,
                    "lexical_candidate_count": 1,
                    "summary_candidate_count": 0,
                    "lexical_fallback": false,
                    "hit_count": 1
                  },
                  "generated_at": "2026-06-06T10:00:00Z"
                }
                """,
            "context/package" =>
                """
                {
                  "query": {"query": "DownloadAsync", "repository_id": "repo:test"},
                  "repository": {"repository_id": "repo:test"},
                  "latest_run": {"run_id": "run:test"},
                  "items": [
                    {
                      "hit": {
                        "node_id": "node:download",
                        "stable_key": "stable:download",
                        "kind": "Method",
                        "file_path": "Downloader.cs",
                        "start_line": 10,
                        "end_line": 20,
                        "score": 0.91
                      },
                      "snippet": "return Task.CompletedTask;",
                      "relationships": [],
                      "relationship_groups": {},
                      "rationale": {"rank": 1}
                    }
                  ],
                  "total_snippet_characters": 26,
                  "generated_at": "2026-06-06T10:00:00Z"
                }
                """,
            "symbols/search" =>
                """
                {
                  "query": {"query": "DownloadAsync", "repository_id": "repo:test"},
                  "symbols": [
                    {
                      "node": {"id": "node:download", "name": "DownloadAsync"},
                      "declaration": null,
                      "score": 0.8,
                      "score_components": {"lexical_score": 0.8}
                    }
                  ],
                  "generated_at": "2026-06-06T10:00:00Z"
                }
                """,
            "nodes/get" =>
                """
                {
                  "node": {"id": "node:download", "kind": "Method"},
                  "content": null,
                  "relationships": []
                }
                """,
            "graph/neighbors" =>
                """
                {
                  "node": {"id": "node:download", "kind": "Method"},
                  "content": null,
                  "relationships": [
                    {"kind": "Invokes", "target_node_id": "node:callee"}
                  ]
                }
                """,
            "repositories?limit=3" =>
                """
                {
                  "repositories": [
                    {
                      "repository_id": "repo:test",
                      "alias": "sample_repo",
                      "root_path": "C:/sample",
                      "remote_url": null,
                      "branch": "main",
                      "commit": "abc123",
                      "first_seen_at": "2026-06-06T09:00:00Z",
                      "last_seen_at": "2026-06-06T10:00:00Z",
                      "last_run_id": "run:test",
                      "last_stage": "Completed",
                      "last_message": null,
                      "node_count": 17,
                      "relationship_count": 28,
                      "content_count": 13,
                      "embedding_count": 17,
                      "metadata": {"alias": "sample_repo"}
                    }
                  ]
                }
                """,
            "repositories/sample%20repo%2Fid" =>
                """
                {
                  "repository_id": "repo:test",
                  "alias": "sample_repo",
                  "root_path": "C:/sample",
                  "remote_url": null,
                  "branch": "main",
                  "commit": "abc123",
                  "first_seen_at": "2026-06-06T09:00:00Z",
                  "last_seen_at": "2026-06-06T10:00:00Z",
                  "last_run_id": "run:test",
                  "last_stage": "Completed",
                  "last_message": null,
                  "node_count": 17,
                  "relationship_count": 28,
                  "content_count": 13,
                  "embedding_count": 17,
                  "metadata": {"alias": "sample_repo"}
                }
                """,
            "repositories/sample%20repo%2Fid/summaries" =>
                """
                {
                  "repository_id": "repo:test",
                  "total_count": 6,
                  "completed_count": 5,
                  "failed_count": 1,
                  "status_counts": {"completed": 5, "failed": 1},
                  "kind_counts": {"Method": 2, "Class": 1, "File": 1, "Property": 1},
                  "provider_model_counts": {"lmstudio/qwen/qwen2.5-coder-14b/node-summary-v1": 6},
                  "provider_model_count_details": [
                    {"provider": "lmstudio", "model": "qwen/qwen2.5-coder-14b", "prompt_version": "node-summary-v1", "count": 6}
                  ],
                  "recent_failures": [
                    {"node_id": "node:failed", "error": "model failed"}
                  ],
                  "generated_at": "2026-06-06T10:10:00Z"
                }
                """,
            "ingestion-runs?limit=2&repository_id=sample%20repo%2Fid" =>
                """
                {
                  "runs": [
                    {
                      "run_id": "run:test",
                      "repository_id": "repo:test",
                      "repository_root": "C:/sample",
                      "stage": "Completed",
                      "started_at": "2026-06-06T09:00:00Z",
                      "finished_at": "2026-06-06T10:00:00Z",
                      "message": null,
                      "language": "csharp",
                      "parser_name": "CodeMesh.Parser.CSharp",
                      "solution_path": "C:/sample/Sample.sln",
                      "project_path": null,
                      "dry_run": false,
                      "skip_embeddings": false,
                      "embedding_provider": "lmstudio",
                      "embedding_model": "text-embedding-nomic-embed-text-v2-moe",
                      "node_count": 17,
                      "relationship_count": 28,
                      "content_count": 13,
                      "embedding_count": 17,
                      "stats": {"parsed_node_count": 17},
                      "diagnostic_count": 0,
                      "error_diagnostic_count": 0,
                      "warning_diagnostic_count": 0,
                      "metadata": {"alias": "sample_repo"}
                    }
                  ]
                }
                """,
            _ => string.Empty
        };

        return string.IsNullOrEmpty(payload)
            ? JsonResponse(HttpStatusCode.NotFound, """{"detail":"not found"}""")
            : JsonResponse(HttpStatusCode.OK, payload);
    }

    private static string DeletePayload(string path)
    {
        return path switch
        {
            "repositories/sample%20repo%2Fid" =>
                """
                {
                  "repository_id": "repo:test",
                  "deleted": true,
                  "registry_entry_existed": true,
                  "graph_cleaned": true,
                  "content_cleaned": true,
                  "embeddings_cleaned": true,
                  "summaries_cleaned": true
                }
                """,
            _ => string.Empty
        };
    }

    private static HttpResponseMessage JsonResponse(HttpStatusCode statusCode, string payload)
        => new(statusCode)
        {
            Content = new StringContent(payload, Encoding.UTF8, "application/json")
        };
}
