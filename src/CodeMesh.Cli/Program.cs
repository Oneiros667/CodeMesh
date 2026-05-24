using System.Text.Json;
using System.Text.Json.Serialization;
using CodeMesh.Control.Diagnostics;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Health;
using CodeMesh.Ingestion;
using CodeMesh.Ingestion.Embedding;
using CodeMesh.Parser.CSharp;
using CodeMesh.Storage;
using CodeMesh.Storage.Mongo;
using CodeMesh.Storage.Neo4j;
using CodeMesh.Storage.Qdrant;

var command = args.FirstOrDefault()?.ToLowerInvariant();

if (command is null or "-h" or "--help" or "help")
{
    PrintHelp();
    return 0;
}

var root = ReadOption(args, "--root") ?? Directory.GetCurrentDirectory();
var json = args.Any(arg => string.Equals(arg, "--json", StringComparison.OrdinalIgnoreCase));
var statusService = new CodeMeshStatusService();

switch (command)
{
    case "doctor":
    {
        var report = await statusService.GetStatusAsync(root).ConfigureAwait(false);
        PrintReport(report, json);
        PrintDoctorAdvice(report, json);
        return report.State == ComponentState.Unhealthy ? 1 : 0;
    }

    case "status":
    {
        var report = await statusService.GetStatusAsync(root).ConfigureAwait(false);
        PrintReport(report, json);
        return 0;
    }

    case "ingest":
    {
        try
        {
            var result = await RunIngestAsync(args).ConfigureAwait(false);
            PrintIngestionResult(result, json);
            return HasErrorDiagnostics(result) ? 1 : 0;
        }
        catch (Exception exception)
        {
            PrintException(exception, json);
            return 1;
        }
    }

    default:
        Console.Error.WriteLine($"Unknown command: {command}");
        PrintHelp();
        return 2;
}

static string? ReadOption(string[] args, string name)
{
    for (var i = 0; i < args.Length - 1; i++)
    {
        if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
        {
            return args[i + 1];
        }
    }

    return null;
}

static bool HasFlag(string[] args, string name)
{
    return args.Any(arg => string.Equals(arg, name, StringComparison.OrdinalIgnoreCase));
}

static string? ReadAnyOption(string[] args, params string[] names)
{
    foreach (var name in names)
    {
        var value = ReadOption(args, name);
        if (!string.IsNullOrWhiteSpace(value))
        {
            return value;
        }
    }

    return null;
}

static async Task<IngestionResult> RunIngestAsync(string[] args)
{
    var repositoryRoot = ReadAnyOption(args, "--root", "--repository-root")
        ?? Directory.GetCurrentDirectory();
    var language = ReadOption(args, "--language") ?? "csharp";

    if (!string.Equals(language, "csharp", StringComparison.OrdinalIgnoreCase))
    {
        throw new InvalidOperationException($"Unsupported ingestion language: {language}. Only csharp is available.");
    }

    var parserClient = CreateParserClient(args);
    await using var graphStore = CreateGraphStore(args);
    var contentStore = CreateContentStore(args);
    using var vectorStore = CreateVectorStore(args);
    var (embeddingProvider, skipEmbeddings) = CreateEmbeddingProvider(args);
    using var disposableEmbeddingProvider = embeddingProvider as IDisposable;

    var request = new IngestionRequest(
        repositoryRoot,
        ReadAnyOption(args, "--solution", "--solution-path"),
        ReadAnyOption(args, "--project", "--project-path"),
        language,
        DryRun: HasFlag(args, "--dry-run"),
        SkipEmbeddings: skipEmbeddings);

    var orchestrator = new IngestionOrchestrator(
        parserClient,
        graphStore,
        contentStore,
        vectorStore,
        embeddingProvider);

    return await orchestrator.IngestAsync(request).ConfigureAwait(false);
}

static IParserClient CreateParserClient(string[] args)
{
    var parserUrl = ReadOption(args, "--parser-url")
        ?? Environment.GetEnvironmentVariable("CODEMESH_CSHARP_PARSER_URL");

    if (!string.IsNullOrWhiteSpace(parserUrl))
    {
        return new HttpParserClient(new HttpClient
        {
            BaseAddress = new Uri(EnsureTrailingSlash(parserUrl), UriKind.Absolute),
            Timeout = TimeSpan.FromMinutes(10)
        });
    }

    return new LocalCSharpParserClient(new CSharpParseService());
}

static Neo4jGraphStore CreateGraphStore(string[] args)
{
    var (user, password) = ReadNeo4jCredentials(args);

    return new Neo4jGraphStore(new Neo4jGraphStoreOptions(
        ReadOption(args, "--neo4j-uri") ?? Environment.GetEnvironmentVariable("CODEMESH_NEO4J_URI") ?? "bolt://localhost:7687",
        user,
        password,
        ReadOption(args, "--neo4j-database") ?? Environment.GetEnvironmentVariable("CODEMESH_NEO4J_DATABASE") ?? "neo4j"));
}

static MongoContentStore CreateContentStore(string[] args)
{
    return new MongoContentStore(new MongoContentStoreOptions(
        ReadOption(args, "--mongo-uri") ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_URI") ?? "mongodb://localhost:27017",
        ReadOption(args, "--mongo-database") ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_DATABASE") ?? "codemesh",
        ReadOption(args, "--mongo-content-collection")
            ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_CONTENT_COLLECTION")
            ?? "content"));
}

static QdrantVectorStore CreateVectorStore(string[] args)
{
    return new QdrantVectorStore(new QdrantVectorStoreOptions(
        ReadOption(args, "--qdrant-url") ?? Environment.GetEnvironmentVariable("CODEMESH_QDRANT_URL") ?? "http://localhost:6333",
        ReadOption(args, "--qdrant-collection") ?? Environment.GetEnvironmentVariable("CODEMESH_QDRANT_COLLECTION") ?? "codemesh-code"));
}

static (IEmbeddingProvider Provider, bool SkipEmbeddings) CreateEmbeddingProvider(string[] args)
{
    var explicitSkip = HasFlag(args, "--skip-embeddings");
    var includeEmbeddings = HasFlag(args, "--include-embeddings");
    if (explicitSkip || !includeEmbeddings)
    {
        return (new NoEmbeddingProvider(), true);
    }

    var provider = ReadOption(args, "--embedding-provider")
        ?? Environment.GetEnvironmentVariable("CODEMESH_MODEL_PROVIDER");
    if (string.IsNullOrWhiteSpace(provider) ||
        string.Equals(provider, "none", StringComparison.OrdinalIgnoreCase))
    {
        provider = "ollama";
    }

    return provider.ToLowerInvariant() switch
    {
        "ollama" => (new OllamaEmbeddingProvider(new OllamaEmbeddingProviderOptions(
            ReadOption(args, "--ollama-url") ?? Environment.GetEnvironmentVariable("CODEMESH_OLLAMA_URL") ?? "http://localhost:11434",
            ReadOption(args, "--embedding-model") ?? Environment.GetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL") ?? "nomic-embed-text:latest",
            BatchSize: ReadIntOption(args, "--embedding-batch-size", 16),
            MaxInputCharacters: ReadIntOption(args, "--embedding-max-chars", 1500))), false),
        _ => throw new InvalidOperationException(
            $"Unsupported embedding provider: {provider}. Supported values: none, ollama.")
    };
}

static int ReadIntOption(string[] args, string name, int defaultValue)
{
    var value = ReadOption(args, name);
    return int.TryParse(value, out var parsed) ? parsed : defaultValue;
}

static (string User, string Password) ReadNeo4jCredentials(string[] args)
{
    var user = ReadOption(args, "--neo4j-user") ?? Environment.GetEnvironmentVariable("CODEMESH_NEO4J_USER");
    var password = ReadOption(args, "--neo4j-password") ?? Environment.GetEnvironmentVariable("CODEMESH_NEO4J_PASSWORD");

    if (!string.IsNullOrWhiteSpace(user) && !string.IsNullOrWhiteSpace(password))
    {
        return (user, password);
    }

    var auth = Environment.GetEnvironmentVariable("CODEMESH_NEO4J_AUTH") ?? "neo4j/codemesh";
    var parts = auth.Split('/', 2);

    return (
        string.IsNullOrWhiteSpace(user) ? parts.ElementAtOrDefault(0) ?? "neo4j" : user,
        string.IsNullOrWhiteSpace(password) ? parts.ElementAtOrDefault(1) ?? "codemesh" : password);
}

static string EnsureTrailingSlash(string value)
{
    return value.EndsWith("/", StringComparison.Ordinal) ? value : $"{value}/";
}

static void PrintReport(HealthReport report, bool json)
{
    if (json)
    {
        Console.WriteLine(JsonSerializer.Serialize(report, new JsonSerializerOptions
        {
            WriteIndented = true,
            Converters = { new JsonStringEnumConverter() }
        }));
        return;
    }

    Console.WriteLine($"CodeMesh status: {report.State}");
    Console.WriteLine($"Checked at: {report.CheckedAt:O}");
    Console.WriteLine();

    foreach (var component in report.Components)
    {
        Console.WriteLine($"{Marker(component.State)} {component.Name}: {component.Message}");
        if (component.Metadata.TryGetValue("path", out var path))
        {
            Console.WriteLine($"    {path}");
        }
        else if (component.Metadata.TryGetValue("endpoint", out var endpoint))
        {
            Console.WriteLine($"    {endpoint}");
        }
    }
}

static void PrintIngestionResult(IngestionResult result, bool json)
{
    if (json)
    {
        Console.WriteLine(JsonSerializer.Serialize(result, JsonOptions()));
        return;
    }

    var mode = result.Run.Message?.StartsWith("Dry run", StringComparison.OrdinalIgnoreCase) == true
        ? "dry-run"
        : "persisted";

    Console.WriteLine($"CodeMesh ingestion: {result.Run.Stage}");
    Console.WriteLine($"Run: {result.Run.RunId}");
    Console.WriteLine($"Repository: {result.Repository.RootPath}");
    Console.WriteLine($"Mode: {mode}");
    if (result.Stats is null)
    {
        Console.WriteLine($"Nodes: {result.NodeCount}");
        Console.WriteLine($"Relationships: {result.RelationshipCount}");
        Console.WriteLine($"Content items: {result.ContentCount}");
        Console.WriteLine($"Embeddings: {result.EmbeddingCount}");
    }
    else
    {
        Console.WriteLine($"Nodes: {result.Stats.ParsedNodeCount} parsed, {result.Stats.WrittenNodeCount} written, {result.Stats.SkippedNodeCount} skipped");
        Console.WriteLine($"Relationships: {result.Stats.ParsedRelationshipCount} parsed, {result.Stats.WrittenRelationshipCount} written, {result.Stats.SkippedRelationshipCount} skipped");
        Console.WriteLine($"Content items: {result.Stats.ParsedContentCount} parsed, {result.Stats.WrittenContentCount} written, {result.Stats.SkippedContentCount} skipped");
        Console.WriteLine($"Embeddings: {result.Stats.WrittenEmbeddingCount} written, {result.Stats.SkippedEmbeddingCount} skipped");
    }

    if (result.Diagnostics.Count == 0)
    {
        Console.WriteLine("Diagnostics: none");
        return;
    }

    Console.WriteLine($"Diagnostics: {result.Diagnostics.Count}");
    foreach (var diagnostic in result.Diagnostics.Take(25))
    {
        Console.WriteLine($"[{diagnostic.Severity}] {diagnostic.Code}: {diagnostic.Message}");
    }

    if (result.Diagnostics.Count > 25)
    {
        Console.WriteLine($"... {result.Diagnostics.Count - 25} more diagnostic(s)");
    }
}

static bool HasErrorDiagnostics(IngestionResult result)
{
    return result.Diagnostics.Any(diagnostic =>
        string.Equals(diagnostic.Severity, "error", StringComparison.OrdinalIgnoreCase));
}

static void PrintException(Exception exception, bool json)
{
    if (json)
    {
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            ok = false,
            error = exception.Message,
            exception = exception.GetType().Name
        }, JsonOptions()));
        return;
    }

    Console.Error.WriteLine($"Ingestion failed: {exception.Message}");
}

static JsonSerializerOptions JsonOptions()
{
    return new JsonSerializerOptions
    {
        WriteIndented = true,
        Converters = { new JsonStringEnumConverter() }
    };
}

static void PrintDoctorAdvice(HealthReport report, bool json)
{
    if (json)
    {
        return;
    }

    Console.WriteLine();

    if (report.Components.Any(component => component.State == ComponentState.Unhealthy))
    {
        Console.WriteLine("Doctor: scaffold files are missing. Re-run the scaffold or restore the listed files.");
        return;
    }

    if (report.Components.Any(component => component.State == ComponentState.Degraded))
    {
        Console.WriteLine("Doctor: scaffold looks present. Start local stores with `docker compose up -d neo4j mongodb qdrant` when you want live storage checks.");
        return;
    }

    Console.WriteLine("Doctor: CodeMesh scaffold is ready.");
}

static string Marker(ComponentState state)
{
    return state switch
    {
        ComponentState.Healthy => "[ok]",
        ComponentState.Degraded => "[warn]",
        ComponentState.Unhealthy => "[fail]",
        ComponentState.NotConfigured => "[skip]",
        _ => "[?]"
    };
}

static void PrintHelp()
{
    Console.WriteLine("CodeMesh CLI");
    Console.WriteLine();
    Console.WriteLine("Usage:");
    Console.WriteLine("  codemesh doctor [--root <path>] [--json]");
    Console.WriteLine("  codemesh status [--root <path>] [--json]");
    Console.WriteLine("  codemesh ingest [--root <path>] [--solution <path>] [--project <path>] [--dry-run] [--skip-embeddings] [--json]");
    Console.WriteLine();
    Console.WriteLine("Ingestion store options:");
    Console.WriteLine("  --neo4j-uri <uri> --neo4j-user <user> --neo4j-password <password> --neo4j-database <database>");
    Console.WriteLine("  --mongo-uri <uri> --mongo-database <database> --mongo-content-collection <collection>");
    Console.WriteLine("  --qdrant-url <url> --qdrant-collection <collection>");
    Console.WriteLine("  --parser-url <url>");
    Console.WriteLine("  --include-embeddings --embedding-provider <none|ollama> --ollama-url <url> --embedding-model <model>");
    Console.WriteLine("  --embedding-batch-size <count> --embedding-max-chars <count>");
}

sealed class LocalCSharpParserClient(CSharpParseService parser) : IParserClient
{
    public Task<ParserCapability> GetCapabilityAsync(CancellationToken cancellationToken = default)
    {
        return Task.FromResult(CSharpParseService.Capability);
    }

    public Task<ParseResult> ParseAsync(ParseRequest request, CancellationToken cancellationToken = default)
    {
        return parser.ParseAsync(request, cancellationToken);
    }
}
