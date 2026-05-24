using System.Net.Http;
using System.Net.Sockets;
using CodeMesh.Control.Configuration;
using CodeMesh.Domain.Health;

namespace CodeMesh.Control.Diagnostics;

public sealed class CodeMeshStatusService
{
    private static readonly TimeSpan TcpProbeTimeout = TimeSpan.FromMilliseconds(750);
    private static readonly TimeSpan HttpProbeTimeout = TimeSpan.FromSeconds(2);
    private static readonly TimeSpan OllamaProbeTimeout = TimeSpan.FromSeconds(5);

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

        components.Add(await CheckTcpAsync("neo4j", "localhost", 7687, cancellationToken).ConfigureAwait(false));
        components.Add(await CheckTcpAsync("mongodb", "localhost", 27017, cancellationToken).ConfigureAwait(false));
        components.Add(await CheckHttpAsync("qdrant", "http://localhost:6333/", false, HttpProbeTimeout, null, cancellationToken).ConfigureAwait(false));
        components.Add(await CheckOllamaAsync(cancellationToken).ConfigureAwait(false));

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
        CancellationToken cancellationToken)
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
                $"Connected to {host}:{port}.",
                new Dictionary<string, string> { ["endpoint"] = $"{host}:{port}" });
        }
        catch (OperationCanceledException)
        {
            return StoreOffline(name, $"{host}:{port}", "Connection timed out.");
        }
        catch (SocketException exception)
        {
            return StoreOffline(name, $"{host}:{port}", exception.Message);
        }
    }

    private static async Task<ComponentHealth> CheckHttpAsync(
        string name,
        string url,
        bool optional,
        TimeSpan timeoutAfter,
        IReadOnlyDictionary<string, string>? metadata,
        CancellationToken cancellationToken)
    {
        try
        {
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            timeout.CancelAfter(timeoutAfter);

            using var http = new HttpClient { Timeout = timeoutAfter };
            using var response = await http.GetAsync(url, timeout.Token).ConfigureAwait(false);

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

            return optional
                ? OptionalOffline(name, url, "Request timed out.", metadata)
                : StoreOffline(name, url, "Request timed out.");
        }
        catch (HttpRequestException exception)
        {
            return optional
                ? OptionalOffline(name, url, exception.Message, metadata)
                : StoreOffline(name, url, exception.Message);
        }
    }

    private static Task<ComponentHealth> CheckOllamaAsync(CancellationToken cancellationToken)
    {
        var baseUrl = Environment.GetEnvironmentVariable("CODEMESH_OLLAMA_URL") ?? "http://localhost:11434";
        var endpoint = OllamaTagsEndpoint(baseUrl);
        var metadata = new Dictionary<string, string>
        {
            ["provider"] = Environment.GetEnvironmentVariable("CODEMESH_MODEL_PROVIDER") ?? "none",
            ["model"] = Environment.GetEnvironmentVariable("CODEMESH_EMBEDDING_MODEL") ?? "nomic-embed-text:latest"
        };

        return CheckHttpAsync("ollama", endpoint, true, OllamaProbeTimeout, metadata, cancellationToken);
    }

    private static string OllamaTagsEndpoint(string baseUrl)
    {
        var trimmed = string.IsNullOrWhiteSpace(baseUrl)
            ? "http://localhost:11434"
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
