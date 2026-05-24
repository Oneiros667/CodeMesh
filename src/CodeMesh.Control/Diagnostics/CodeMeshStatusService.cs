using System.Net.Http;
using System.Net.Sockets;
using CodeMesh.Control.Configuration;
using CodeMesh.Domain.Health;

namespace CodeMesh.Control.Diagnostics;

public sealed class CodeMeshStatusService
{
    private static readonly TimeSpan ProbeTimeout = TimeSpan.FromMilliseconds(750);

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
        components.Add(await CheckHttpAsync("qdrant", "http://localhost:6333/", false, cancellationToken).ConfigureAwait(false));
        components.Add(await CheckHttpAsync("ollama", "http://localhost:11434/api/tags", true, cancellationToken).ConfigureAwait(false));

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
            timeout.CancelAfter(ProbeTimeout);

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
        CancellationToken cancellationToken)
    {
        try
        {
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            timeout.CancelAfter(ProbeTimeout);

            using var http = new HttpClient { Timeout = ProbeTimeout };
            using var response = await http.GetAsync(url, timeout.Token).ConfigureAwait(false);

            var state = response.IsSuccessStatusCode ? ComponentState.Healthy : ComponentState.Degraded;
            return new ComponentHealth(
                name,
                state,
                $"HTTP {(int)response.StatusCode} from {url}.",
                new Dictionary<string, string> { ["endpoint"] = url });
        }
        catch (OperationCanceledException)
        {
            return optional
                ? OptionalOffline(name, url)
                : StoreOffline(name, url, "Request timed out.");
        }
        catch (HttpRequestException exception)
        {
            return optional
                ? OptionalOffline(name, url)
                : StoreOffline(name, url, exception.Message);
        }
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

    private static ComponentHealth OptionalOffline(string name, string endpoint)
    {
        return new ComponentHealth(
            name,
            ComponentState.NotConfigured,
            "Optional local model provider is not running.",
            new Dictionary<string, string> { ["endpoint"] = endpoint });
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
