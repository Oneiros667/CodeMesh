using System.Net;
using System.Net.Sockets;
using System.Text;
using CodeMesh.Control.Diagnostics;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Health;
using CodeMesh.Domain.Utilities;
using CodeMesh.Ingestion;
using CodeMesh.Ingestion.Embedding;
using CodeMesh.Parser.CSharp;
using CodeMesh.Storage.Memory;
using CodeMesh.Storage.Mongo;
using CodeMesh.Storage.Neo4j;
using CodeMesh.Storage.Qdrant;

var tests = new (string Name, Func<Task> Run)[]
{
    ("sha256 helper is deterministic", TestHash),
    ("ingestion writes parser output", TestIngestionWritesParserOutput),
    ("dry-run ingestion skips stores", TestDryRunSkipsStores),
    ("repository refresh removes stale records", TestRepositoryRefreshRemovesStaleRecords),
    ("incremental ingestion skips unchanged records", TestIncrementalIngestionSkipsUnchangedRecords),
    ("status uses configured ollama endpoint", TestStatusUsesConfiguredOllamaEndpoint),
    ("ollama embedding provider maps responses", TestOllamaEmbeddingProviderMapsResponses),
    ("mongodb content store round-trips content", TestMongoContentStoreRoundTripsContent),
    ("neo4j graph store round-trips graph", TestNeo4jGraphStoreRoundTripsGraph),
    ("qdrant vector store round-trips embeddings", TestQdrantVectorStoreRoundTripsEmbeddings),
    ("csharp parser emits Roslyn symbols", TestCSharpParserEmitsRoslynSymbols),
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
}

static async Task TestMongoContentStoreRoundTripsContent()
{
    var store = new MongoContentStore(new MongoContentStoreOptions(
        Environment.GetEnvironmentVariable("CODEMESH_MONGO_URI") ?? "mongodb://localhost:27017",
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

static async Task TestNeo4jGraphStoreRoundTripsGraph()
{
    var uri = Environment.GetEnvironmentVariable("CODEMESH_NEO4J_URI") ?? "bolt://localhost:7687";
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
    var url = Environment.GetEnvironmentVariable("CODEMESH_QDRANT_URL") ?? "http://localhost:6333";
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
        ?? @"C:\Users\developer\source\repos\YoutubeDownloader";
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

    public SlowHttpServer(TimeSpan delay)
    {
        _delay = delay;
        _listener = new TcpListener(IPAddress.Loopback, 0);
        _listener.Start();

        var endpoint = (IPEndPoint)_listener.LocalEndpoint;
        BaseUrl = $"http://127.0.0.1:{endpoint.Port}";
        _serverTask = Task.Run(ServeAsync);
    }

    public string BaseUrl { get; }

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

        await Task.Delay(_delay, cancellationToken).ConfigureAwait(false);

        const string body = """{"models":[]}""";
        var response = Encoding.ASCII.GetBytes(
            $"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {body.Length}\r\nConnection: close\r\n\r\n{body}");
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

sealed class FakeOllamaEmbeddingHandler : HttpMessageHandler
{
    public int RequestCount { get; private set; }

    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        RequestCount++;

        if (request.RequestUri?.AbsolutePath != "/api/embed")
        {
            return Task.FromResult(new HttpResponseMessage(System.Net.HttpStatusCode.NotFound));
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

        return Task.FromResult(response);
    }
}
