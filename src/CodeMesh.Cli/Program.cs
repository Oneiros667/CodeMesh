using System.Text.Json;
using System.Text.Json.Serialization;
using CodeMesh.Control.AgentAccess;
using CodeMesh.Control.Configuration;
using CodeMesh.Control.Diagnostics;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Health;
using CodeMesh.Domain.Utilities;
using CodeMesh.Ingestion;
using CodeMesh.Ingestion.Embedding;
using CodeMesh.Ingestion.Summary;
using CodeMesh.Parser.CSharp;
using CodeMesh.Parser.Markdown;
using CodeMesh.Parser.Python;
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
EnvironmentFileLoader.LoadIfExists(root);
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

    case "refresh":
    {
        try
        {
            var result = await RunRefreshAsync(args).ConfigureAwait(false);
            PrintIngestionResult(result, json);
            return HasErrorDiagnostics(result) ? 1 : 0;
        }
        catch (Exception exception)
        {
            PrintException(exception, json);
            return 1;
        }
    }

    case "self":
    {
        try
        {
            var subcommand = ReadPositional(args, 1)?.ToLowerInvariant();
            switch (subcommand)
            {
                case "ingest":
                {
                    var result = await RunSelfIngestAsync(args).ConfigureAwait(false);
                    PrintIngestionResult(result, json);
                    return HasErrorDiagnostics(result) ? 1 : 0;
                }

                case "smoke":
                {
                    var result = await RunSelfSmokeAsync(args).ConfigureAwait(false);
                    PrintSelfSmokeResult(result, json);
                    return result.Success ? 0 : 1;
                }

                default:
                    throw new InvalidOperationException("Usage: codemesh self ingest [options] | codemesh self smoke [options]");
            }
        }
        catch (Exception exception)
        {
            PrintException(exception, json);
            return 1;
        }
    }

    case "embeddings":
    {
        try
        {
            var subcommand = ReadPositional(args, 1)?.ToLowerInvariant();
            if (subcommand is not "verify")
            {
                throw new InvalidOperationException("Usage: codemesh embeddings verify <repository-id-or-alias> [--embedding-provider <provider>] [--embedding-model <model>]");
            }

            var result = await RunEmbeddingVerificationAsync(args).ConfigureAwait(false);
            PrintEmbeddingVerification(result, json);
            return result.IsComplete ? 0 : 1;
        }
        catch (Exception exception)
        {
            PrintException(exception, json);
            return 1;
        }
    }

    case "summaries":
    {
        try
        {
            var subcommand = ReadPositional(args, 1)?.ToLowerInvariant();
            if (subcommand is not "coverage")
            {
                throw new InvalidOperationException("Usage: codemesh summaries coverage <repository-id-or-alias>");
            }

            var coverage = await RunSummaryCoverageAsync(args).ConfigureAwait(false);
            PrintSummaryCoverage(coverage, json);
            return 0;
        }
        catch (Exception exception)
        {
            PrintException(exception, json);
            return 1;
        }
    }

    case "repos":
    {
        try
        {
            var store = CreateRegistryStore(args);
            var repositories = await store
                .ListRepositoriesAsync(ReadIntOption(args, "--limit", 50))
                .ConfigureAwait(false);
            PrintRepositoryList(repositories, json);
            return 0;
        }
        catch (Exception exception)
        {
            PrintException(exception, json);
            return 1;
        }
    }

    case "repo":
    {
        try
        {
            var subcommand = ReadPositional(args, 1)?.ToLowerInvariant();
            switch (subcommand)
            {
                case "show":
                {
                    var repositoryId = ReadPositional(args, 2)
                        ?? throw new InvalidOperationException("Repository id or alias is required. Usage: codemesh repo show <repository-id-or-alias>");
                    var store = CreateRegistryStore(args);
                    var repository = await store
                        .GetRepositoryAsync(repositoryId)
                        .ConfigureAwait(false);
                    PrintRepository(repository, json);
                    return repository is null ? 1 : 0;
                }

                case "delete":
                {
                    var result = await RunRepositoryDeleteAsync(args).ConfigureAwait(false);
                    PrintRepositoryCleanup(result, json);
                    return 0;
                }

                default:
                    throw new InvalidOperationException("Usage: codemesh repo show <repository-id-or-alias> | codemesh repo delete <repository-id-or-alias>");
            }
        }
        catch (Exception exception)
        {
            PrintException(exception, json);
            return 1;
        }
    }

    case "runs":
    {
        try
        {
            var store = CreateRegistryStore(args);
            var repositoryRef = ReadAnyOption(args, "--repository-id", "--repo");
            var repositoryId = await ResolveRepositoryIdAsync(store, repositoryRef).ConfigureAwait(false);
            var runs = await store
                .ListRunsAsync(repositoryId, ReadIntOption(args, "--limit", 50))
                .ConfigureAwait(false);
            PrintRunList(runs, json);
            return 0;
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

static string? ReadPositional(string[] args, int index)
{
    return args.Length > index && !args[index].StartsWith("--", StringComparison.Ordinal)
        ? args[index]
        : null;
}

static async Task<IngestionResult> RunIngestAsync(string[] args)
{
    var repositoryRoot = ReadAnyOption(args, "--root", "--repository-root")
        ?? Directory.GetCurrentDirectory();
    var language = ReadOption(args, "--language") ?? "csharp";
    var forceEmbeddings = HasFlag(args, "--force-embeddings");

    if (!IsSupportedLanguage(language))
    {
        throw new InvalidOperationException($"Unsupported ingestion language: {language}. Supported values: csharp, markdown, python.");
    }

    var parserClient = CreateParserClient(args);
    await using var graphStore = CreateGraphStore(args);
    var contentStore = CreateContentStore(args);
    var registryStore = CreateRegistryStore(args);
    using var vectorStore = CreateVectorStore(args);
    var (embeddingProvider, skipEmbeddings) = CreateEmbeddingProvider(args);
    using var disposableEmbeddingProvider = embeddingProvider as IDisposable;
    var (summaryProvider, includeSummaries) = CreateSummaryProvider(args);
    using var disposableSummaryProvider = summaryProvider as IDisposable;

    var request = new IngestionRequest(
        repositoryRoot,
        ReadAnyOption(args, "--solution", "--solution-path"),
        ReadAnyOption(args, "--project", "--project-path"),
        language,
        DryRun: HasFlag(args, "--dry-run"),
        SkipEmbeddings: skipEmbeddings,
        ForceEmbeddings: forceEmbeddings,
        IncludeSummaries: includeSummaries,
        ForceSummaries: HasFlag(args, "--force-summaries"));

    var orchestrator = new IngestionOrchestrator(
        parserClient,
        graphStore,
        contentStore,
        vectorStore,
        embeddingProvider,
        registryStore,
        CreateNodeSummaryStore(args),
        summaryProvider);

    return await orchestrator.IngestAsync(request).ConfigureAwait(false);
}

static async Task<IngestionResult> RunRefreshAsync(string[] args)
{
    var target = CodeMeshRefreshWorkflow.ResolveTarget(
        ReadAnyOption(args, "--root", "--repository-root"),
        ReadAnyOption(args, "--solution", "--solution-path"),
        ReadAnyOption(args, "--project", "--project-path"),
        ReadOption(args, "--language"));

    return await RunIngestAsync(CodeMeshRefreshWorkflow.BuildRefreshIngestArgs(args, target)).ConfigureAwait(false);
}

static async Task<IngestionResult> RunSelfIngestAsync(string[] args)
{
    var target = CodeMeshSelfWorkflow.ResolveTarget(ReadAnyOption(args, "--root", "--repository-root"), ReadAnyOption(args, "--solution", "--solution-path"));
    return await RunIngestAsync(CodeMeshSelfWorkflow.BuildSelfIngestArgs(args, target)).ConfigureAwait(false);
}

static async Task<SelfSmokeResult> RunSelfSmokeAsync(string[] args)
{
    if (HasFlag(args, "--dry-run"))
    {
        throw new InvalidOperationException("codemesh self smoke requires persistent ingestion. Use `codemesh self ingest --dry-run` to validate parsing only.");
    }

    var target = CodeMeshSelfWorkflow.ResolveTarget(ReadAnyOption(args, "--root", "--repository-root"), ReadAnyOption(args, "--solution", "--solution-path"));
    var ingestArgs = CodeMeshSelfWorkflow.BuildSelfIngestArgs(args, target);
    var ingest = await RunIngestAsync(ingestArgs).ConfigureAwait(false);

    if (HasErrorDiagnostics(ingest))
    {
        return new SelfSmokeResult(
            false,
            ingest.Repository.Id,
            RepositoryAlias.FromPath(ingest.Repository.RootPath),
            target.RootPath,
            target.SolutionPath,
            "Ingestion completed with error diagnostics.",
            ingest.NodeCount,
            ingest.RelationshipCount,
            ingest.ContentCount,
            ingest.EmbeddingCount,
            ingest.SummaryCount,
            0,
            0,
            null);
    }

    using var client = new AgentAccessClient(new AgentAccessClientOptions(
        ReadOption(args, "--agent-access-url") ?? Environment.GetEnvironmentVariable("CODEMESH_AGENT_ACCESS_URL") ?? "http://127.0.0.1:8088",
        TimeSpan.FromSeconds(ReadIntOption(args, "--agent-timeout-seconds", 30))));

    var repositories = await client.ListRepositoriesAsync(100).ConfigureAwait(false);
    var repository = repositories.Repositories.FirstOrDefault(item =>
        string.Equals(item.RepositoryId, ingest.Repository.Id, StringComparison.Ordinal) ||
        string.Equals(item.Alias, RepositoryAlias.FromPath(ingest.Repository.RootPath), StringComparison.OrdinalIgnoreCase));
    if (repository is null)
    {
        return new SelfSmokeResult(
            false,
            ingest.Repository.Id,
            RepositoryAlias.FromPath(ingest.Repository.RootPath),
            target.RootPath,
            target.SolutionPath,
            "Agent Access did not list the self-ingested repository.",
            ingest.NodeCount,
            ingest.RelationshipCount,
            ingest.ContentCount,
            ingest.EmbeddingCount,
            ingest.SummaryCount,
            repositories.Repositories.Count,
            0,
            null);
    }

    var runs = await client.ListIngestionRunsAsync(ingest.Repository.Id, 5).ConfigureAwait(false);
    if (runs.Runs.Count == 0)
    {
        return new SelfSmokeResult(
            false,
            ingest.Repository.Id,
            repository.Alias,
            target.RootPath,
            target.SolutionPath,
            "Agent Access did not list ingestion runs for the self-ingested repository.",
            ingest.NodeCount,
            ingest.RelationshipCount,
            ingest.ContentCount,
            ingest.EmbeddingCount,
            ingest.SummaryCount,
            repositories.Repositories.Count,
            0,
            null);
    }

    var query = ReadOption(args, "--query") ?? "IngestionOrchestrator";
    var context = await client.SearchContextAsync(new AgentContextQuery(
        query,
        RepositoryId: ingest.Repository.Id,
        Limit: ReadIntOption(args, "--limit", 5),
        Kinds: ["Class", "Method"],
        Filters: new Dictionary<string, string>())).ConfigureAwait(false);

    if (context.Hits.Count == 0)
    {
        return new SelfSmokeResult(
            false,
            ingest.Repository.Id,
            repository.Alias,
            target.RootPath,
            target.SolutionPath,
            $"Agent Access context search returned no hits for '{query}'.",
            ingest.NodeCount,
            ingest.RelationshipCount,
            ingest.ContentCount,
            ingest.EmbeddingCount,
            ingest.SummaryCount,
            repositories.Repositories.Count,
            runs.Runs.Count,
            query);
    }

    return new SelfSmokeResult(
        true,
        ingest.Repository.Id,
        repository.Alias,
        target.RootPath,
        target.SolutionPath,
        "Self-ingestion smoke completed.",
        ingest.NodeCount,
        ingest.RelationshipCount,
        ingest.ContentCount,
        ingest.EmbeddingCount,
        ingest.SummaryCount,
        repositories.Repositories.Count,
        runs.Runs.Count,
        query,
        context.Hits.Count,
        context.Diagnostics?.Mode);
}

static async Task<EmbeddingVerificationResult> RunEmbeddingVerificationAsync(string[] args)
{
    var repositoryId = ReadAnyOption(args, "--repository-id", "--repo")
        ?? ReadPositional(args, 2)
        ?? throw new InvalidOperationException("Repository id or alias is required. Usage: codemesh embeddings verify <repository-id-or-alias>");
    var (provider, model) = ResolveEmbeddingTarget(args);
    var registryStore = CreateRegistryStore(args);
    var resolvedRepositoryId = await ResolveRepositoryIdAsync(registryStore, repositoryId, ignoreResolutionErrors: true).ConfigureAwait(false)
        ?? repositoryId;

    await using var graphStore = CreateGraphStore(args);
    using var vectorStore = CreateVectorStore(args);
    var verifier = new EmbeddingVerifier(graphStore, vectorStore);

    return await verifier
        .VerifyAsync(new EmbeddingVerificationRequest(resolvedRepositoryId, provider, model))
        .ConfigureAwait(false);
}

static async Task<NodeSummaryCoverage> RunSummaryCoverageAsync(string[] args)
{
    var repositoryId = ReadAnyOption(args, "--repository-id", "--repo")
        ?? ReadPositional(args, 2)
        ?? throw new InvalidOperationException("Repository id or alias is required. Usage: codemesh summaries coverage <repository-id-or-alias>");
    var registryStore = CreateRegistryStore(args);
    var resolvedRepositoryId = await ResolveRepositoryIdAsync(registryStore, repositoryId, ignoreResolutionErrors: true)
        .ConfigureAwait(false) ?? repositoryId;
    var summaryStore = CreateNodeSummaryStore(args);

    return await summaryStore
        .GetSummaryCoverageAsync(resolvedRepositoryId)
        .ConfigureAwait(false);
}

static async Task<RepositoryCleanupResult> RunRepositoryDeleteAsync(string[] args)
{
    var repositoryRef = ReadAnyOption(args, "--repository-id", "--repo")
        ?? ReadPositional(args, 2)
        ?? throw new InvalidOperationException("Repository id or alias is required. Usage: codemesh repo delete <repository-id-or-alias>");
    var registryStore = CreateRegistryStore(args);
    var repository = await registryStore
        .GetRepositoryAsync(repositoryRef)
        .ConfigureAwait(false)
        ?? throw new InvalidOperationException($"Repository not found: {repositoryRef}");

    await using var graphStore = CreateGraphStore(args);
    var contentStore = CreateContentStore(args);
    using var vectorStore = CreateVectorStore(args);
    var summaryStore = CreateNodeSummaryStore(args);
    var cleanup = new RepositoryCleanupService(
        graphStore,
        contentStore,
        vectorStore,
        registryStore,
        summaryStore);

    return await cleanup
        .DeleteRepositoryAsync(repository.RepositoryId)
        .ConfigureAwait(false);
}

static async Task<string?> ResolveRepositoryIdAsync(
    IRegistryStore store,
    string? repositoryRef,
    bool ignoreResolutionErrors = false)
{
    if (string.IsNullOrWhiteSpace(repositoryRef))
    {
        return null;
    }

    try
    {
        var repository = await store
            .GetRepositoryAsync(repositoryRef)
            .ConfigureAwait(false);

        return repository?.RepositoryId ?? repositoryRef;
    }
    catch when (ignoreResolutionErrors)
    {
        return repositoryRef;
    }
}

static IParserClient CreateParserClient(string[] args)
{
    var language = ReadOption(args, "--language") ?? "csharp";
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

    return NormalizeLanguage(language) switch
    {
        "csharp" => new LocalCSharpParserClient(new CSharpParseService()),
        "markdown" => new LocalMarkdownParserClient(new MarkdownParseService()),
        "python" => new LocalPythonParserClient(new PythonParseService()),
        _ => throw new InvalidOperationException($"Unsupported ingestion language: {language}. Supported values: csharp, markdown, python.")
    };
}

static bool IsSupportedLanguage(string language)
{
    return NormalizeLanguage(language) is "csharp" or "markdown" or "python";
}

static string NormalizeLanguage(string language)
{
    return language.Trim().ToLowerInvariant() switch
    {
        "cs" or "c#" => "csharp",
        "md" => "markdown",
        "py" => "python",
        var value => value
    };
}

static Neo4jGraphStore CreateGraphStore(string[] args)
{
    var (user, password) = ReadNeo4jCredentials(args);

    return new Neo4jGraphStore(new Neo4jGraphStoreOptions(
        ReadOption(args, "--neo4j-uri") ?? Environment.GetEnvironmentVariable("CODEMESH_NEO4J_URI") ?? "bolt://127.0.0.1:7687",
        user,
        password,
        ReadOption(args, "--neo4j-database") ?? Environment.GetEnvironmentVariable("CODEMESH_NEO4J_DATABASE") ?? "neo4j"));
}

static MongoContentStore CreateContentStore(string[] args)
{
    return new MongoContentStore(new MongoContentStoreOptions(
        ReadOption(args, "--mongo-uri") ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_URI") ?? "mongodb://127.0.0.1:27017",
        ReadOption(args, "--mongo-database") ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_DATABASE") ?? "codemesh",
        ReadOption(args, "--mongo-content-collection")
            ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_CONTENT_COLLECTION")
            ?? "content"));
}

static MongoRegistryStore CreateRegistryStore(string[] args)
{
    return new MongoRegistryStore(new MongoRegistryStoreOptions(
        ReadOption(args, "--mongo-uri") ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_URI") ?? "mongodb://127.0.0.1:27017",
        ReadOption(args, "--mongo-database") ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_DATABASE") ?? "codemesh",
        ReadOption(args, "--mongo-repositories-collection")
            ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_REPOSITORIES_COLLECTION")
            ?? "repositories",
        ReadOption(args, "--mongo-ingestion-runs-collection")
            ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_INGESTION_RUNS_COLLECTION")
            ?? "ingestion_runs"));
}

static MongoNodeSummaryStore CreateNodeSummaryStore(string[] args)
{
    return new MongoNodeSummaryStore(new MongoNodeSummaryStoreOptions(
        ReadOption(args, "--mongo-uri") ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_URI") ?? "mongodb://127.0.0.1:27017",
        ReadOption(args, "--mongo-database") ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_DATABASE") ?? "codemesh",
        ReadOption(args, "--mongo-node-summaries-collection")
            ?? Environment.GetEnvironmentVariable("CODEMESH_MONGO_NODE_SUMMARIES_COLLECTION")
            ?? "node_summaries"));
}

static QdrantVectorStore CreateVectorStore(string[] args)
{
    return new QdrantVectorStore(new QdrantVectorStoreOptions(
        ReadOption(args, "--qdrant-url") ?? Environment.GetEnvironmentVariable("CODEMESH_QDRANT_URL") ?? "http://127.0.0.1:6333",
        ReadOption(args, "--qdrant-collection") ?? Environment.GetEnvironmentVariable("CODEMESH_QDRANT_COLLECTION") ?? "codemesh-code"));
}

static (IEmbeddingProvider Provider, bool SkipEmbeddings) CreateEmbeddingProvider(string[] args)
{
    var explicitSkip = HasFlag(args, "--skip-embeddings");
    var forceEmbeddings = HasFlag(args, "--force-embeddings");
    var includeEmbeddings = HasFlag(args, "--include-embeddings") || forceEmbeddings;
    if (explicitSkip && forceEmbeddings)
    {
        throw new InvalidOperationException("--skip-embeddings cannot be combined with --force-embeddings.");
    }

    if (explicitSkip || !includeEmbeddings)
    {
        return (new NoEmbeddingProvider(), true);
    }

    var (provider, model) = ResolveEmbeddingTarget(args);
    if (string.Equals(provider, "none", StringComparison.OrdinalIgnoreCase))
    {
        throw new InvalidOperationException(
            "Embedding provider 'none' cannot be used when embeddings are included. Supported values: ollama, lmstudio.");
    }

    return NormalizeEmbeddingProvider(provider) switch
    {
        "ollama" => (new OllamaEmbeddingProvider(new OllamaEmbeddingProviderOptions(
            ReadOption(args, "--ollama-url") ?? Environment.GetEnvironmentVariable("CODEMESH_OLLAMA_URL") ?? "http://127.0.0.1:11434",
            model,
            BatchSize: ReadIntOption(args, "--embedding-batch-size", 16),
            MaxInputCharacters: ReadIntOption(args, "--embedding-max-chars", 1500))), false),
        "lmstudio" => (new LmStudioEmbeddingProvider(new LmStudioEmbeddingProviderOptions(
            ReadAnyOption(args, "--lm-studio-url", "--lmstudio-url")
                ?? Environment.GetEnvironmentVariable("CODEMESH_LM_STUDIO_URL")
                ?? "http://127.0.0.1:1234/v1",
            model,
            BatchSize: ReadIntOption(args, "--embedding-batch-size", 16),
            MaxInputCharacters: ReadIntOption(args, "--embedding-max-chars", 1500))), false),
        _ => throw new InvalidOperationException(
            $"Unsupported embedding provider: {provider}. Supported values: none, ollama, lmstudio.")
    };
}

static (ICodeSummaryProvider Provider, bool IncludeSummaries) CreateSummaryProvider(string[] args)
{
    var includeSummaries = HasFlag(args, "--include-summaries") || HasFlag(args, "--force-summaries");
    if (!includeSummaries)
    {
        return (new NoCodeSummaryProvider(), false);
    }

    var provider = ReadOption(args, "--summary-provider")
        ?? Environment.GetEnvironmentVariable("CODEMESH_SUMMARY_PROVIDER")
        ?? Environment.GetEnvironmentVariable("CODEMESH_MODEL_PROVIDER")
        ?? "ollama";
    provider = NormalizeModelProvider(provider);
    if (string.Equals(provider, "none", StringComparison.OrdinalIgnoreCase))
    {
        throw new InvalidOperationException(
            "Summary provider 'none' cannot be used when summaries are included. Supported values: ollama, lmstudio.");
    }

    var model = ReadOption(args, "--summary-model")
        ?? Environment.GetEnvironmentVariable("CODEMESH_SUMMARY_MODEL")
        ?? DefaultSummaryModel(provider);

    return provider switch
    {
        "ollama" => (new OllamaCodeSummaryProvider(new OllamaCodeSummaryProviderOptions(
            ReadOption(args, "--ollama-url") ?? Environment.GetEnvironmentVariable("CODEMESH_OLLAMA_URL") ?? "http://127.0.0.1:11434",
            model)), true),
        "lmstudio" => (new LmStudioCodeSummaryProvider(new LmStudioCodeSummaryProviderOptions(
            ReadAnyOption(args, "--lm-studio-url", "--lmstudio-url")
                ?? Environment.GetEnvironmentVariable("CODEMESH_LM_STUDIO_URL")
                ?? "http://127.0.0.1:1234/v1",
            model)), true),
        _ => throw new InvalidOperationException(
            $"Unsupported summary provider: {provider}. Supported values: ollama, lmstudio.")
    };
}

static (string Provider, string Model) ResolveEmbeddingTarget(string[] args)
{
    var provider = ReadOption(args, "--embedding-provider")
        ?? Environment.GetEnvironmentVariable("CODEMESH_MODEL_PROVIDER");
    if (string.IsNullOrWhiteSpace(provider) ||
        string.Equals(provider, "none", StringComparison.OrdinalIgnoreCase))
    {
        provider = "ollama";
    }
    provider = NormalizeModelProvider(provider);

    var model = ReadOption(args, "--embedding-model")
        ?? Environment.GetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL");
    if (string.IsNullOrWhiteSpace(model))
    {
        model = DefaultEmbeddingModel(provider);
    }

    return (provider, model);
}

static string NormalizeEmbeddingProvider(string provider)
{
    return NormalizeModelProvider(provider);
}

static string NormalizeModelProvider(string provider)
{
    return provider.Trim().ToLowerInvariant() switch
    {
        "lm-studio" or "lm_studio" => "lmstudio",
        var value => value
    };
}

static string DefaultSummaryModel(string provider)
{
    return NormalizeModelProvider(provider) == "lmstudio"
        ? "mistralai/ministral-3-3b"
        : "qwen2.5-coder:14b";
}

static string DefaultEmbeddingModel(string provider)
{
    return NormalizeEmbeddingProvider(provider) == "lmstudio"
        ? "text-embedding-nomic-embed-text-v2-moe"
        : "nomic-embed-text-v2-moe:latest";
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
        Console.WriteLine($"Summaries: {result.SummaryCount}");
    }
    else
    {
        Console.WriteLine($"Nodes: {result.Stats.ParsedNodeCount} parsed, {result.Stats.WrittenNodeCount} written, {result.Stats.SkippedNodeCount} skipped");
        Console.WriteLine($"Relationships: {result.Stats.ParsedRelationshipCount} parsed, {result.Stats.WrittenRelationshipCount} written, {result.Stats.SkippedRelationshipCount} skipped");
        Console.WriteLine($"Content items: {result.Stats.ParsedContentCount} parsed, {result.Stats.WrittenContentCount} written, {result.Stats.SkippedContentCount} skipped");
        Console.WriteLine($"Embeddings: {result.Stats.WrittenEmbeddingCount} written, {result.Stats.SkippedEmbeddingCount} skipped");
        Console.WriteLine($"Summaries: {result.Stats.WrittenSummaryCount} written, {result.Stats.SkippedSummaryCount} skipped, {result.Stats.FailedSummaryCount} failed, {result.Stats.SummaryCandidateCount} candidates");
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

static void PrintRepositoryList(IReadOnlyList<RepositoryIndexRecord> repositories, bool json)
{
    if (json)
    {
        Console.WriteLine(JsonSerializer.Serialize(repositories, JsonOptions()));
        return;
    }

    if (repositories.Count == 0)
    {
        Console.WriteLine("No indexed repositories found.");
        return;
    }

    foreach (var repository in repositories)
    {
        Console.WriteLine($"{repository.RepositoryId}");
        if (!string.IsNullOrWhiteSpace(repository.Alias))
        {
            Console.WriteLine($"  alias: {repository.Alias}");
        }

        Console.WriteLine($"  root: {repository.RootPath}");
        Console.WriteLine($"  last run: {repository.LastRunId ?? "-"} ({repository.LastStage?.ToString() ?? "unknown"})");
        Console.WriteLine($"  last seen: {repository.LastSeenAt:O}");
        Console.WriteLine($"  nodes: {repository.NodeCount}, relationships: {repository.RelationshipCount}, content: {repository.ContentCount}, embeddings: {repository.EmbeddingCount?.ToString() ?? "unknown"}");
    }
}

static void PrintRepository(RepositoryIndexRecord? repository, bool json)
{
    if (json)
    {
        Console.WriteLine(JsonSerializer.Serialize(repository, JsonOptions()));
        return;
    }

    if (repository is null)
    {
        Console.WriteLine("Repository not found.");
        return;
    }

    Console.WriteLine($"Repository: {repository.RepositoryId}");
    if (!string.IsNullOrWhiteSpace(repository.Alias))
    {
        Console.WriteLine($"Alias: {repository.Alias}");
    }

    Console.WriteLine($"Root: {repository.RootPath}");
    Console.WriteLine($"First seen: {repository.FirstSeenAt:O}");
    Console.WriteLine($"Last seen: {repository.LastSeenAt:O}");
    Console.WriteLine($"Last run: {repository.LastRunId ?? "-"}");
    Console.WriteLine($"Last stage: {repository.LastStage?.ToString() ?? "unknown"}");
    Console.WriteLine($"Last message: {repository.LastMessage ?? "-"}");
    Console.WriteLine($"Nodes: {repository.NodeCount}");
    Console.WriteLine($"Relationships: {repository.RelationshipCount}");
    Console.WriteLine($"Content items: {repository.ContentCount}");
    Console.WriteLine($"Embeddings: {repository.EmbeddingCount?.ToString() ?? "unknown"}");
}

static void PrintEmbeddingVerification(EmbeddingVerificationResult result, bool json)
{
    if (json)
    {
        Console.WriteLine(JsonSerializer.Serialize(result, JsonOptions()));
        return;
    }

    Console.WriteLine($"CodeMesh embeddings: {(result.IsComplete ? "Complete" : "Incomplete")}");
    Console.WriteLine($"Repository: {result.RepositoryId}");
    Console.WriteLine($"Provider/model: {result.Provider}/{result.Model}");
    Console.WriteLine($"Expected nodes: {result.ExpectedCount}");
    Console.WriteLine($"Embeddings: {result.CurrentEmbeddingCount} current, {result.MatchingEmbeddingCount} matching provider/model, {result.TotalRepositoryEmbeddingCount} total");
    Console.WriteLine($"Other provider/model embeddings: {result.OtherProviderEmbeddingCount}");
    Console.WriteLine($"Issues: {result.MissingCount} missing, {result.OutdatedCount} outdated, {result.StaleCount} stale, {result.DuplicateCount} duplicate");
    var otherIssueCount = result.Issues.Count - result.MissingCount - result.OutdatedCount - result.StaleCount - result.DuplicateCount;
    if (otherIssueCount > 0)
    {
        Console.WriteLine($"Other issues: {otherIssueCount}");
    }

    foreach (var issue in result.Issues.Take(25))
    {
        Console.WriteLine($"[{issue.Kind}] {issue.NodeId}");
        if (!string.IsNullOrWhiteSpace(issue.ExpectedContentHash))
        {
            Console.WriteLine($"  expected: {issue.ExpectedContentHash}");
        }

        if (!string.IsNullOrWhiteSpace(issue.ActualContentHash))
        {
            Console.WriteLine($"  actual: {issue.ActualContentHash}");
        }

        if (!string.IsNullOrWhiteSpace(issue.EmbeddingId))
        {
            Console.WriteLine($"  embedding: {issue.EmbeddingId}");
        }

        Console.WriteLine($"  {issue.Message}");
    }

    if (result.Issues.Count > 25)
    {
        Console.WriteLine($"... {result.Issues.Count - 25} more issue(s)");
    }
}

static void PrintSummaryCoverage(NodeSummaryCoverage coverage, bool json)
{
    if (json)
    {
        Console.WriteLine(JsonSerializer.Serialize(coverage, JsonOptions()));
        return;
    }

    Console.WriteLine("CodeMesh summaries:");
    Console.WriteLine($"Repository: {coverage.RepositoryId}");
    Console.WriteLine($"Summaries: {coverage.TotalCount} total, {coverage.CompletedCount} completed, {coverage.FailedCount} failed");
    PrintCountGroup("Statuses", coverage.StatusCounts);
    PrintCountGroup("Kinds", coverage.KindCounts);
    PrintProviderModelDetails(coverage);

    if (coverage.RecentFailures.Count == 0)
    {
        Console.WriteLine("Recent failures: none");
        return;
    }

    Console.WriteLine("Recent failures:");
    foreach (var failure in coverage.RecentFailures.Take(10))
    {
        Console.WriteLine($"  [{failure.GeneratedAt:O}] {failure.NodeId} ({failure.Kind})");
        Console.WriteLine($"    provider/model: {failure.Provider}/{failure.Model}");
        Console.WriteLine($"    error: {failure.Error}");
    }
}

static void PrintSelfSmokeResult(SelfSmokeResult result, bool json)
{
    if (json)
    {
        Console.WriteLine(JsonSerializer.Serialize(result, JsonOptions()));
        return;
    }

    Console.WriteLine($"CodeMesh self smoke: {(result.Success ? "Passed" : "Failed")}");
    Console.WriteLine($"Repository: {result.RepositoryId}");
    if (!string.IsNullOrWhiteSpace(result.Alias))
    {
        Console.WriteLine($"Alias: {result.Alias}");
    }

    Console.WriteLine($"Root: {result.RootPath}");
    Console.WriteLine($"Solution: {result.SolutionPath}");
    Console.WriteLine($"Nodes: {result.NodeCount}, relationships: {result.RelationshipCount}, content: {result.ContentCount}, embeddings: {result.EmbeddingCount}, summaries: {result.SummaryCount}");
    Console.WriteLine($"Agent repositories visible: {result.VisibleRepositoryCount}");
    Console.WriteLine($"Recent runs: {result.RecentRunCount}");
    if (!string.IsNullOrWhiteSpace(result.Query))
    {
        Console.WriteLine($"Context query: {result.Query}");
        Console.WriteLine($"Context hits: {result.ContextHitCount}");
        Console.WriteLine($"Search mode: {result.SearchMode ?? "unknown"}");
    }

    Console.WriteLine($"Message: {result.Message}");
}

static void PrintProviderModelDetails(NodeSummaryCoverage coverage)
{
    if (coverage.ProviderModelCountDetails.Count > 0)
    {
        Console.WriteLine("Provider/model/prompt:");
        foreach (var detail in coverage.ProviderModelCountDetails)
        {
            Console.WriteLine($"  provider: {detail.Provider}");
            Console.WriteLine($"    model: {detail.Model}");
            Console.WriteLine($"    prompt: {detail.PromptVersion}");
            Console.WriteLine($"    count: {detail.Count}");
        }

        return;
    }

    PrintCountGroup("Provider/model/prompt", coverage.ProviderModelCounts);
}

static void PrintRepositoryCleanup(RepositoryCleanupResult result, bool json)
{
    if (json)
    {
        Console.WriteLine(JsonSerializer.Serialize(result, JsonOptions()));
        return;
    }

    Console.WriteLine("CodeMesh repository deleted:");
    Console.WriteLine($"Repository: {result.RepositoryId}");
    Console.WriteLine($"Registry entry existed: {result.RegistryEntryExisted}");
    Console.WriteLine($"Graph cleaned: {result.GraphCleaned}");
    Console.WriteLine($"Content cleaned: {result.ContentCleaned}");
    Console.WriteLine($"Embeddings cleaned: {result.EmbeddingsCleaned}");
    Console.WriteLine($"Summaries cleaned: {result.SummariesCleaned}");
}

static void PrintCountGroup(string label, IReadOnlyDictionary<string, int> counts)
{
    if (counts.Count == 0)
    {
        Console.WriteLine($"{label}: none");
        return;
    }

    Console.WriteLine($"{label}:");
    foreach (var (key, count) in counts)
    {
        Console.WriteLine($"  {key}: {count}");
    }
}

static void PrintRunList(IReadOnlyList<IngestionRunIndexRecord> runs, bool json)
{
    if (json)
    {
        Console.WriteLine(JsonSerializer.Serialize(runs, JsonOptions()));
        return;
    }

    if (runs.Count == 0)
    {
        Console.WriteLine("No ingestion runs found.");
        return;
    }

    foreach (var run in runs)
    {
        Console.WriteLine($"{run.RunId}");
        Console.WriteLine($"  repository: {run.RepositoryId}");
        Console.WriteLine($"  stage: {run.Stage}");
        Console.WriteLine($"  started: {run.StartedAt:O}");
        Console.WriteLine($"  finished: {run.FinishedAt:O}");
        Console.WriteLine($"  parser: {run.ParserName} ({run.Language})");
        Console.WriteLine($"  embeddings: {run.EmbeddingProvider}/{run.EmbeddingModel}, written: {run.EmbeddingCount}");
        Console.WriteLine($"  nodes: {run.NodeCount}, relationships: {run.RelationshipCount}, content: {run.ContentCount}");
        Console.WriteLine($"  diagnostics: {run.DiagnosticCount} ({run.ErrorDiagnosticCount} error, {run.WarningDiagnosticCount} warning)");
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

    Console.Error.WriteLine($"Command failed: {exception.Message}");
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
    Console.WriteLine("  codemesh ingest [--root <path>] [--solution <path>] [--project <path>] [--language <csharp|markdown|python>] [--dry-run] [--skip-embeddings] [--force-embeddings] [--include-summaries] [--json]");
    Console.WriteLine("  codemesh refresh [--root <path>] [--solution <path>] [--project <path>] [--language <csharp|markdown|python>] [--skip-embeddings] [--force-embeddings] [--include-summaries] [--json]");
    Console.WriteLine("  codemesh self ingest [--dry-run] [--skip-embeddings] [--include-embeddings] [--include-summaries] [--json]");
    Console.WriteLine("  codemesh self smoke [--agent-access-url <url>] [--skip-embeddings] [--query <text>] [--json]");
    Console.WriteLine("  codemesh embeddings verify <repository-id-or-alias> [--embedding-provider <provider>] [--embedding-model <model>] [--json]");
    Console.WriteLine("  codemesh summaries coverage <repository-id-or-alias> [--json]");
    Console.WriteLine("  codemesh repos list [--limit <count>] [--json]");
    Console.WriteLine("  codemesh repo show <repository-id-or-alias> [--json]");
    Console.WriteLine("  codemesh repo delete <repository-id-or-alias> [--json]");
    Console.WriteLine("  codemesh runs list [--repository-id <id-or-alias>] [--limit <count>] [--json]");
    Console.WriteLine();
    Console.WriteLine("Ingestion store options:");
    Console.WriteLine("  --neo4j-uri <uri> --neo4j-user <user> --neo4j-password <password> --neo4j-database <database>");
    Console.WriteLine("  --mongo-uri <uri> --mongo-database <database> --mongo-content-collection <collection>");
    Console.WriteLine("  --mongo-repositories-collection <collection> --mongo-ingestion-runs-collection <collection> --mongo-node-summaries-collection <collection>");
    Console.WriteLine("  --qdrant-url <url> --qdrant-collection <collection>");
    Console.WriteLine("  --parser-url <url>");
    Console.WriteLine("  --include-embeddings --embedding-provider <none|ollama|lmstudio> --ollama-url <url> --lm-studio-url <url> --embedding-model <model>");
    Console.WriteLine("  --embedding-batch-size <count> --embedding-max-chars <count>");
    Console.WriteLine("  --include-summaries --force-summaries --summary-provider <ollama|lmstudio> --summary-model <model>");
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

sealed class LocalMarkdownParserClient(MarkdownParseService parser) : IParserClient
{
    public Task<ParserCapability> GetCapabilityAsync(CancellationToken cancellationToken = default)
    {
        return Task.FromResult(MarkdownParseService.Capability);
    }

    public Task<ParseResult> ParseAsync(ParseRequest request, CancellationToken cancellationToken = default)
    {
        return parser.ParseAsync(request, cancellationToken);
    }
}

sealed class LocalPythonParserClient(PythonParseService parser) : IParserClient
{
    public Task<ParserCapability> GetCapabilityAsync(CancellationToken cancellationToken = default)
    {
        return Task.FromResult(PythonParseService.Capability);
    }

    public Task<ParseResult> ParseAsync(ParseRequest request, CancellationToken cancellationToken = default)
    {
        return parser.ParseAsync(request, cancellationToken);
    }
}

sealed record SelfSmokeResult(
    bool Success,
    string RepositoryId,
    string? Alias,
    string RootPath,
    string SolutionPath,
    string Message,
    int NodeCount,
    int RelationshipCount,
    int ContentCount,
    int EmbeddingCount,
    int SummaryCount,
    int VisibleRepositoryCount,
    int RecentRunCount,
    string? Query,
    int ContextHitCount = 0,
    string? SearchMode = null);
