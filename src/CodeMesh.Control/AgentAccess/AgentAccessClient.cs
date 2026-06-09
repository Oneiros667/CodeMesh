using System.Net.Http.Json;
using System.Text.Json;
using CodeMesh.Domain.Contracts;

namespace CodeMesh.Control.AgentAccess;

public sealed record AgentAccessClientOptions(
    string BaseUrl = "http://127.0.0.1:8088",
    TimeSpan? Timeout = null);

public interface IAgentAccessClient
{
    Task<AgentHealthResult> GetHealthAsync(CancellationToken cancellationToken = default);

    Task<AgentHealthResult> GetStatusAsync(CancellationToken cancellationToken = default);

    Task<AgentContextResult> SearchContextAsync(AgentContextQuery query, CancellationToken cancellationToken = default);

    Task<AgentContextPackageResult> GetContextPackageAsync(AgentContextPackageQuery query, CancellationToken cancellationToken = default);

    Task<AgentSymbolSearchResult> SearchSymbolsAsync(AgentSymbolQuery query, CancellationToken cancellationToken = default);

    Task<AgentNodeResult> GetNodeAsync(AgentNodeLookup lookup, CancellationToken cancellationToken = default);

    Task<AgentNeighborResult> GetNeighborsAsync(AgentNeighborQuery query, CancellationToken cancellationToken = default);

    Task<AgentRepositoryListResult> ListRepositoriesAsync(int limit = 50, CancellationToken cancellationToken = default);

    Task<AgentRepositorySummary?> GetRepositoryAsync(string repositoryId, CancellationToken cancellationToken = default);

    Task<AgentIngestionRunListResult> ListIngestionRunsAsync(
        string? repositoryId = null,
        int limit = 50,
        CancellationToken cancellationToken = default);
}

public sealed class AgentAccessClient : IAgentAccessClient, IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly HttpClient _http;
    private readonly bool _ownsHttpClient;

    public AgentAccessClient(AgentAccessClientOptions options)
        : this(CreateHttpClient(options), ownsHttpClient: true)
    {
    }

    public AgentAccessClient(HttpClient httpClient, bool ownsHttpClient = false)
    {
        _http = httpClient;
        _ownsHttpClient = ownsHttpClient;
    }

    public Task<AgentHealthResult> GetHealthAsync(CancellationToken cancellationToken = default)
        => GetAsync<AgentHealthResult>("health", cancellationToken);

    public Task<AgentHealthResult> GetStatusAsync(CancellationToken cancellationToken = default)
        => GetAsync<AgentHealthResult>("status", cancellationToken);

    public Task<AgentContextResult> SearchContextAsync(
        AgentContextQuery query,
        CancellationToken cancellationToken = default)
        => PostAsync<AgentContextQuery, AgentContextResult>("context/search", query, cancellationToken);

    public Task<AgentContextPackageResult> GetContextPackageAsync(
        AgentContextPackageQuery query,
        CancellationToken cancellationToken = default)
        => PostAsync<AgentContextPackageQuery, AgentContextPackageResult>("context/package", query, cancellationToken);

    public Task<AgentSymbolSearchResult> SearchSymbolsAsync(
        AgentSymbolQuery query,
        CancellationToken cancellationToken = default)
        => PostAsync<AgentSymbolQuery, AgentSymbolSearchResult>("symbols/search", query, cancellationToken);

    public Task<AgentNodeResult> GetNodeAsync(
        AgentNodeLookup lookup,
        CancellationToken cancellationToken = default)
        => PostAsync<AgentNodeLookup, AgentNodeResult>("nodes/get", lookup, cancellationToken);

    public Task<AgentNeighborResult> GetNeighborsAsync(
        AgentNeighborQuery query,
        CancellationToken cancellationToken = default)
        => PostAsync<AgentNeighborQuery, AgentNeighborResult>("graph/neighbors", query, cancellationToken);

    public Task<AgentRepositoryListResult> ListRepositoriesAsync(
        int limit = 50,
        CancellationToken cancellationToken = default)
        => GetAsync<AgentRepositoryListResult>($"repositories?limit={limit}", cancellationToken);

    public Task<AgentRepositorySummary?> GetRepositoryAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
        => GetAsync<AgentRepositorySummary?>($"repositories/{Uri.EscapeDataString(repositoryId)}", cancellationToken);

    public Task<AgentIngestionRunListResult> ListIngestionRunsAsync(
        string? repositoryId = null,
        int limit = 50,
        CancellationToken cancellationToken = default)
    {
        var path = $"ingestion-runs?limit={limit}";
        if (!string.IsNullOrWhiteSpace(repositoryId))
        {
            path += $"&repository_id={Uri.EscapeDataString(repositoryId)}";
        }

        return GetAsync<AgentIngestionRunListResult>(path, cancellationToken);
    }

    public void Dispose()
    {
        if (_ownsHttpClient)
        {
            _http.Dispose();
        }
    }

    private async Task<TResponse> PostAsync<TRequest, TResponse>(
        string path,
        TRequest request,
        CancellationToken cancellationToken)
    {
        using var response = await _http
            .PostAsJsonAsync(path, request, JsonOptions, cancellationToken)
            .ConfigureAwait(false);

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
            throw new InvalidOperationException(
                $"Agent Access request to '{path}' failed with HTTP {(int)response.StatusCode}: {body}");
        }

        var result = await response.Content
            .ReadFromJsonAsync<TResponse>(JsonOptions, cancellationToken)
            .ConfigureAwait(false);

        return result ?? throw new InvalidOperationException(
            $"Agent Access request to '{path}' returned an empty response.");
    }

    private async Task<TResponse> GetAsync<TResponse>(
        string path,
        CancellationToken cancellationToken)
    {
        using var response = await _http.GetAsync(path, cancellationToken).ConfigureAwait(false);

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
            throw new InvalidOperationException(
                $"Agent Access request to '{path}' failed with HTTP {(int)response.StatusCode}: {body}");
        }

        var result = await response.Content
            .ReadFromJsonAsync<TResponse>(JsonOptions, cancellationToken)
            .ConfigureAwait(false);

        return result ?? throw new InvalidOperationException(
            $"Agent Access request to '{path}' returned an empty response.");
    }

    private static HttpClient CreateHttpClient(AgentAccessClientOptions options)
    {
        var baseUrl = options.BaseUrl.EndsWith("/", StringComparison.Ordinal)
            ? options.BaseUrl
            : $"{options.BaseUrl}/";

        return new HttpClient
        {
            BaseAddress = new Uri(baseUrl, UriKind.Absolute),
            Timeout = options.Timeout ?? TimeSpan.FromSeconds(30)
        };
    }
}
