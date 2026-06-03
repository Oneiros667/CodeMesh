using System.Net;
using System.Net.Http;
using System.Net.Sockets;
using CodeMesh.Control.Configuration;
using CodeMesh.Domain.Health;

namespace CodeMesh.Control.Diagnostics;

public sealed class CodeMeshStatusService
{
    private const string DefaultOllamaUrl = "http://127.0.0.1:11434";
    private const string DefaultLmStudioUrl = "http://127.0.0.1:1234/v1";

    private static readonly TimeSpan TcpProbeTimeout = TimeSpan.FromMilliseconds(750);
    private static readonly TimeSpan RequiredProbeRetryDelay = TimeSpan.FromMilliseconds(150);
    private static readonly TimeSpan HttpProbeTimeout = TimeSpan.FromSeconds(2);
    private static readonly TimeSpan OllamaProbeTimeout = TimeSpan.FromSeconds(2);
    private static readonly TimeSpan OllamaRetryDelay = TimeSpan.FromMilliseconds(250);

    public async Task<HealthReport> GetStatusAsync(
        string? rootPath = null,
        CancellationToken cancellationToken = default)
    {
        var workspace = CodeMeshWorkspace.Discover(rootPath);
        var components = new List<ComponentHealth>
        {
            CheckFile("config", workspace.ConfigPath, "codemesh.yaml"),
            CheckFile("compose", workspace.ComposePath, "docker-compose.yml"),
            CheckFile("env-example", workspace.EnvExamplePath, ".env.example"),
            CheckDirectory("agent-access", workspace.AgentAccessPath, "Python Agent Access service")
        };

        components.Add(await CheckTcpAsync(
            "neo4j",
            "127.0.0.1",
            7687,
            cancellationToken,
            attempts: 2,
            retryDelay: RequiredProbeRetryDelay).ConfigureAwait(false));
        components.Add(await CheckTcpAsync(
            "mongodb",
            "127.0.0.1",
            27017,
            cancellationToken,
            attempts: 2,
            retryDelay: RequiredProbeRetryDelay).ConfigureAwait(false));
        components.Add(await CheckHttpAsync(
            "qdrant",
            "http://127.0.0.1:6333/",
            false,
            HttpProbeTimeout,
            null,
            cancellationToken,
            attempts: 2,
            retryDelay: RequiredProbeRetryDelay).ConfigureAwait(false));
        components.Add(await CheckModelProviderAsync(cancellationToken).ConfigureAwait(false));

        return new HealthReport(
            "codemesh",
            Aggregate(components),
            components,
            DateTimeOffset.UtcNow);
    }

    private static ComponentHealth CheckFile(string name, string path, string label)
    {
        if (File.Exists(path))
        {
            return new ComponentHealth(
                name,
                ComponentState.Healthy,
                $"{label} exists.",
                new Dictionary<string, string> { ["path"] = path });
        }

        return new ComponentHealth(
            name,
            ComponentState.Unhealthy,
            $"{label} is missing.",
            new Dictionary<string, string> { ["path"] = path });
    }

    private static ComponentHealth CheckDirectory(string name, string path, string label)
    {
        if (Directory.Exists(path))
        {
            return new ComponentHealth(
                name,
                ComponentState.Healthy,
                $"{label} directory exists.",
                new Dictionary<string, string> { ["path"] = path });
        }

        return new ComponentHealth(
            name,
            ComponentState.Unhealthy,
            $"{label} directory is missing.",
            new Dictionary<string, string> { ["path"] = path });
    }

    private static async Task<ComponentHealth> CheckTcpAsync(
        string name,
        string host,
        int port,
        CancellationToken cancellationToken,
        int attempts = 1,
        TimeSpan? retryDelay = null)
    {
        var endpoint = $"{host}:{port}";
        var maxAttempts = Math.Max(1, attempts);
        for (var attempt = 1; attempt <= maxAttempts; attempt++)
        {
            try
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                timeout.CancelAfter(TcpProbeTimeout);

                using var client = new TcpClient();
                await client.ConnectAsync(host, port, timeout.Token).ConfigureAwait(false);

                return new ComponentHealth(
                    name,
                    ComponentState.Healthy,
                    $"Connected to {endpoint}.",
                    new Dictionary<string, string> { ["endpoint"] = endpoint });
            }
            catch (OperationCanceledException)
            {
                if (cancellationToken.IsCancellationRequested)
                {
                    throw;
                }

                if (attempt < maxAttempts)
                {
                    await DelayBeforeRetryAsync(retryDelay, cancellationToken).ConfigureAwait(false);
                    continue;
                }

                return StoreOffline(name, endpoint, "Connection timed out.");
            }
            catch (SocketException exception)
            {
                if (attempt < maxAttempts)
                {
                    await DelayBeforeRetryAsync(retryDelay, cancellationToken).ConfigureAwait(false);
                    continue;
                }

                return StoreOffline(name, endpoint, exception.Message);
            }
        }

        return StoreOffline(name, endpoint, "Connection failed.");
    }

    private static async Task<ComponentHealth> CheckHttpAsync(
        string name,
        string url,
        bool optional,
        TimeSpan timeoutAfter,
        IReadOnlyDictionary<string, string>? metadata,
        CancellationToken cancellationToken,
        int attempts = 1,
        TimeSpan? retryDelay = null)
    {
        var maxAttempts = Math.Max(1, attempts);
        for (var attempt = 1; attempt <= maxAttempts; attempt++)
        {
            try
            {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
                timeout.CancelAfter(timeoutAfter);

                using var http = new HttpClient { Timeout = timeoutAfter };
                using var response = await http.GetAsync(url, timeout.Token).ConfigureAwait(false);

                if (!response.IsSuccessStatusCode && attempt < maxAttempts && IsRetryableStatus(response.StatusCode))
                {
                    await DelayBeforeRetryAsync(retryDelay, cancellationToken).ConfigureAwait(false);
                    continue;
                }

                var responseMetadata = MetadataWithEndpoint(url, metadata);
                var state = response.IsSuccessStatusCode ? ComponentState.Healthy : ComponentState.Degraded;
                return new ComponentHealth(
                    name,
                    state,
                    $"HTTP {(int)response.StatusCode} from {url}.",
                    responseMetadata);
            }
            catch (OperationCanceledException)
            {
                if (cancellationToken.IsCancellationRequested)
                {
                    throw;
                }

                if (attempt < maxAttempts)
                {
                    await DelayBeforeRetryAsync(retryDelay, cancellationToken).ConfigureAwait(false);
                    continue;
                }

                return optional
                    ? OptionalOffline(name, url, "Request timed out.", metadata)
                    : StoreOffline(name, url, "Request timed out.");
            }
            catch (HttpRequestException exception)
            {
                if (attempt < maxAttempts)
                {
                    await DelayBeforeRetryAsync(retryDelay, cancellationToken).ConfigureAwait(false);
                    continue;
                }

                return optional
                    ? OptionalOffline(name, url, exception.Message, metadata)
                    : StoreOffline(name, url, exception.Message);
            }
        }

        return optional
            ? OptionalOffline(name, url, "Request failed.", metadata)
            : StoreOffline(name, url, "Request failed.");
    }

    private static Task<ComponentHealth> CheckModelProviderAsync(CancellationToken cancellationToken)
    {
        var provider = NormalizeModelProvider(Environment.GetEnvironmentVariable("CODEMESH_MODEL_PROVIDER") ?? "none");
        return provider switch
        {
            "lmstudio" => CheckLmStudioAsync(cancellationToken),
            "none" or "ollama" => CheckOllamaAsync(cancellationToken),
            _ => Task.FromResult(OptionalOffline(
                "model-provider",
                provider,
                "Unsupported local model provider.",
                ModelProviderMetadata(provider)))
        };
    }

    private static async Task<ComponentHealth> CheckOllamaAsync(CancellationToken cancellationToken)
    {
        var baseUrl = Environment.GetEnvironmentVariable("CODEMESH_OLLAMA_URL") ?? DefaultOllamaUrl;
        var endpoints = OllamaTagsEndpoints(baseUrl);
        var metadata = ModelProviderMetadata(Environment.GetEnvironmentVariable("CODEMESH_MODEL_PROVIDER") ?? "none");

        ComponentHealth? last = null;
        for (var index = 0; index < endpoints.Count; index++)
        {
            var attempts = endpoints.Count > 1 && index == 0 ? 1 : 3;
            var health = await CheckHttpAsync(
                "ollama",
                endpoints[index],
                true,
                OllamaProbeTimeout,
                metadata,
                cancellationToken,
                attempts,
                OllamaRetryDelay).ConfigureAwait(false);

            if (health.State == ComponentState.Healthy)
            {
                return health;
            }

            last = health;
        }

        return last ?? OptionalOffline("ollama", endpoints[0], "Request failed.", metadata);
    }

    private static async Task<ComponentHealth> CheckLmStudioAsync(CancellationToken cancellationToken)
    {
        var baseUrl = Environment.GetEnvironmentVariable("CODEMESH_LM_STUDIO_URL") ?? DefaultLmStudioUrl;
        var endpoint = LmStudioModelsEndpoint(baseUrl);
        var metadata = ModelProviderMetadata("lmstudio");

        return await CheckHttpAsync(
            "lmstudio",
            endpoint,
            true,
            OllamaProbeTimeout,
            metadata,
            cancellationToken,
            attempts: 3,
            retryDelay: OllamaRetryDelay).ConfigureAwait(false);
    }

    private static bool IsRetryableStatus(HttpStatusCode statusCode)
    {
        var code = (int)statusCode;
        return statusCode == HttpStatusCode.RequestTimeout || code >= 500;
    }

    private static async Task DelayBeforeRetryAsync(TimeSpan? retryDelay, CancellationToken cancellationToken)
    {
        var delay = retryDelay ?? TimeSpan.Zero;
        if (delay <= TimeSpan.Zero)
        {
            return;
        }

        await Task.Delay(delay, cancellationToken).ConfigureAwait(false);
    }

    private static IReadOnlyList<string> OllamaTagsEndpoints(string baseUrl)
    {
        var endpoint = OllamaTagsEndpoint(baseUrl);
        if (!Uri.TryCreate(endpoint, UriKind.Absolute, out var uri) ||
            !string.Equals(uri.Host, "localhost", StringComparison.OrdinalIgnoreCase))
        {
            return [endpoint];
        }

        var fallback = new UriBuilder(uri) { Host = "127.0.0.1" }.Uri.ToString();
        return string.Equals(endpoint, fallback, StringComparison.OrdinalIgnoreCase)
            ? [endpoint]
            : [endpoint, fallback];
    }

    private static string OllamaTagsEndpoint(string baseUrl)
    {
        var trimmed = string.IsNullOrWhiteSpace(baseUrl)
            ? DefaultOllamaUrl
            : baseUrl.Trim();

        if (trimmed.EndsWith("/api/tags", StringComparison.OrdinalIgnoreCase))
        {
            return trimmed;
        }

        if (trimmed.EndsWith("/api", StringComparison.OrdinalIgnoreCase))
        {
            return $"{trimmed}/tags";
        }

        return $"{trimmed.TrimEnd('/')}/api/tags";
    }

    private static string LmStudioModelsEndpoint(string baseUrl)
    {
        var trimmed = string.IsNullOrWhiteSpace(baseUrl)
            ? DefaultLmStudioUrl
            : baseUrl.Trim();

        if (trimmed.EndsWith("/models", StringComparison.OrdinalIgnoreCase))
        {
            return trimmed;
        }

        return $"{trimmed.TrimEnd('/')}/models";
    }

    private static IReadOnlyDictionary<string, string> ModelProviderMetadata(string provider)
    {
        var normalizedProvider = NormalizeModelProvider(provider);
        return new Dictionary<string, string>
        {
            ["provider"] = normalizedProvider,
            ["model"] = Environment.GetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL")
                ?? DefaultEmbeddingModel(normalizedProvider)
        };
    }

    private static string NormalizeModelProvider(string provider)
    {
        return provider.Trim().ToLowerInvariant() switch
        {
            "lm-studio" or "lm_studio" => "lmstudio",
            var value => value
        };
    }

    private static string DefaultEmbeddingModel(string provider)
    {
        return NormalizeModelProvider(provider) == "lmstudio"
            ? "text-embedding-nomic-embed-text-v1.5"
            : "nomic-embed-text:latest";
    }

    private static ComponentHealth StoreOffline(string name, string endpoint, string detail)
    {
        return new ComponentHealth(
            name,
            ComponentState.Degraded,
            "Default store endpoint is not reachable.",
            new Dictionary<string, string>
            {
                ["endpoint"] = endpoint,
                ["detail"] = detail
            });
    }

    private static ComponentHealth OptionalOffline(
        string name,
        string endpoint,
        string detail,
        IReadOnlyDictionary<string, string>? metadata)
    {
        return new ComponentHealth(
            name,
            ComponentState.NotConfigured,
            "Optional local model provider is not running.",
            MetadataWithEndpoint(endpoint, metadata, detail));
    }

    private static Dictionary<string, string> MetadataWithEndpoint(
        string endpoint,
        IReadOnlyDictionary<string, string>? metadata,
        string? detail = null)
    {
        var values = metadata is null
            ? new Dictionary<string, string>(StringComparer.Ordinal)
            : new Dictionary<string, string>(metadata, StringComparer.Ordinal);
        values["endpoint"] = endpoint;

        if (!string.IsNullOrWhiteSpace(detail))
        {
            values["detail"] = detail;
        }

        return values;
    }

    private static ComponentState Aggregate(IReadOnlyCollection<ComponentHealth> components)
    {
        if (components.Any(component => component.State == ComponentState.Unhealthy))
        {
            return ComponentState.Unhealthy;
        }

        if (components.Any(component => component.State == ComponentState.Degraded))
        {
            return ComponentState.Degraded;
        }

        if (components.All(component => component.State == ComponentState.NotConfigured))
        {
            return ComponentState.NotConfigured;
        }

        return ComponentState.Healthy;
    }
}
