using System.Net;
using System.Net.Http.Json;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Health;

namespace CodeMesh.Storage.Qdrant;

public sealed record QdrantVectorStoreOptions(
    string Url,
    string CollectionName = "codemesh-code",
    string Distance = "Cosine",
    TimeSpan? Timeout = null);

public sealed class QdrantVectorStore : IVectorStore, IStoreHealthCheck, IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly HttpClient _http;
    private readonly bool _ownsHttpClient;
    private readonly SemaphoreSlim _collectionLock = new(1, 1);
    private bool _collectionReady;

    public QdrantVectorStore(QdrantVectorStoreOptions options)
        : this(CreateHttpClient(options), options.CollectionName, options.Distance, ownsHttpClient: true)
    {
    }

    public QdrantVectorStore(
        HttpClient httpClient,
        string collectionName = "codemesh-code",
        string distance = "Cosine",
        bool ownsHttpClient = false)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(collectionName);
        ArgumentException.ThrowIfNullOrWhiteSpace(distance);

        _http = httpClient;
        CollectionName = collectionName;
        Distance = distance;
        _ownsHttpClient = ownsHttpClient;
        Name = $"qdrant:{collectionName}";
    }

    public string Name { get; }

    public string CollectionName { get; }

    public string Distance { get; }

    public async Task UpsertEmbeddingsAsync(
        IReadOnlyList<EmbeddingRecord> embeddings,
        CancellationToken cancellationToken = default)
    {
        if (embeddings.Count == 0)
        {
            return;
        }

        var dimensions = embeddings[0].Dimensions;
        if (dimensions <= 0)
        {
            throw new InvalidOperationException("Embedding dimensions must be greater than zero.");
        }

        foreach (var embedding in embeddings)
        {
            if (embedding.Dimensions != dimensions || embedding.Vector.Count != dimensions)
            {
                throw new InvalidOperationException("All embeddings in a Qdrant upsert batch must have matching dimensions.");
            }
        }

        await EnsureCollectionAsync(dimensions, cancellationToken).ConfigureAwait(false);

        var request = new UpsertRequest(
            embeddings.Select(embedding => new PointStruct(
                PointIdFor(embedding.Id),
                embedding.Vector,
                ToPayload(embedding))).ToArray());

        using var response = await _http
            .PutAsJsonAsync($"collections/{Uri.EscapeDataString(CollectionName)}/points?wait=true", request, JsonOptions, cancellationToken)
            .ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
    }

    public async Task<IReadOnlyList<VectorSearchMatch>> SearchAsync(
        IReadOnlyList<float> vector,
        int limit,
        IReadOnlyDictionary<string, string>? filters = null,
        CancellationToken cancellationToken = default)
    {
        if (vector.Count == 0 || limit <= 0)
        {
            return Array.Empty<VectorSearchMatch>();
        }

        if (!await CollectionExistsAsync(cancellationToken).ConfigureAwait(false))
        {
            return Array.Empty<VectorSearchMatch>();
        }

        var request = new SearchRequest(
            vector,
            limit,
            WithPayload: true,
            Filter: BuildFilter(filters));

        using var response = await _http
            .PostAsJsonAsync($"collections/{Uri.EscapeDataString(CollectionName)}/points/search", request, JsonOptions, cancellationToken)
            .ConfigureAwait(false);
        response.EnsureSuccessStatusCode();

        var result = await response.Content
            .ReadFromJsonAsync<SearchResponse>(JsonOptions, cancellationToken)
            .ConfigureAwait(false);

        return result?.Result
            .Select(match => new VectorSearchMatch(
                PayloadString(match.Payload, "nodeId"),
                PayloadString(match.Payload, "contentHash"),
                match.Score,
                PayloadNullableString(match.Payload, "preview"),
                PayloadMetadata(match.Payload)))
            .ToArray() ?? Array.Empty<VectorSearchMatch>();
    }

    public async Task<ComponentHealth> CheckAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            using var response = await _http.GetAsync("collections", cancellationToken)
                .ConfigureAwait(false);

            var metadata = new Dictionary<string, string>
            {
                ["url"] = _http.BaseAddress?.ToString() ?? string.Empty,
                ["collection"] = CollectionName
            };

            if (response.IsSuccessStatusCode)
            {
                return new ComponentHealth(
                    Name,
                    ComponentState.Healthy,
                    "Qdrant vector store is available.",
                    metadata);
            }

            metadata["statusCode"] = ((int)response.StatusCode).ToString();
            return new ComponentHealth(
                Name,
                ComponentState.Degraded,
                "Qdrant vector store returned an unhealthy status.",
                metadata);
        }
        catch (Exception exception) when (exception is HttpRequestException or TaskCanceledException)
        {
            return new ComponentHealth(
                Name,
                ComponentState.Degraded,
                "Qdrant vector store is not reachable.",
                new Dictionary<string, string>
                {
                    ["url"] = _http.BaseAddress?.ToString() ?? string.Empty,
                    ["collection"] = CollectionName,
                    ["detail"] = exception.Message
                });
        }
    }

    public void Dispose()
    {
        _collectionLock.Dispose();
        if (_ownsHttpClient)
        {
            _http.Dispose();
        }
    }

    private async Task EnsureCollectionAsync(int dimensions, CancellationToken cancellationToken)
    {
        if (_collectionReady)
        {
            return;
        }

        await _collectionLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_collectionReady)
            {
                return;
            }

            if (!await CollectionExistsAsync(cancellationToken).ConfigureAwait(false))
            {
                var request = new CreateCollectionRequest(new VectorParams(dimensions, Distance));
                using var response = await _http
                    .PutAsJsonAsync($"collections/{Uri.EscapeDataString(CollectionName)}", request, JsonOptions, cancellationToken)
                    .ConfigureAwait(false);
                response.EnsureSuccessStatusCode();
            }

            _collectionReady = true;
        }
        finally
        {
            _collectionLock.Release();
        }
    }

    private async Task<bool> CollectionExistsAsync(CancellationToken cancellationToken)
    {
        using var response = await _http
            .GetAsync($"collections/{Uri.EscapeDataString(CollectionName)}", cancellationToken)
            .ConfigureAwait(false);

        if (response.StatusCode == HttpStatusCode.NotFound)
        {
            return false;
        }

        response.EnsureSuccessStatusCode();
        return true;
    }

    private static HttpClient CreateHttpClient(QdrantVectorStoreOptions options)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(options.Url);

        var baseAddress = options.Url.EndsWith("/", StringComparison.Ordinal)
            ? options.Url
            : $"{options.Url}/";

        return new HttpClient
        {
            BaseAddress = new Uri(baseAddress, UriKind.Absolute),
            Timeout = options.Timeout ?? TimeSpan.FromSeconds(10)
        };
    }

    private static string PointIdFor(string embeddingId)
    {
        if (Guid.TryParse(embeddingId, out var parsed))
        {
            return parsed.ToString("D");
        }

        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(embeddingId));
        bytes[7] = (byte)((bytes[7] & 0x0F) | 0x40);
        bytes[8] = (byte)((bytes[8] & 0x3F) | 0x80);
        return new Guid(bytes[..16]).ToString("D");
    }

    private static Dictionary<string, object> ToPayload(EmbeddingRecord embedding)
    {
        var payload = new Dictionary<string, object>(StringComparer.Ordinal)
        {
            ["embeddingId"] = embedding.Id,
            ["nodeId"] = embedding.NodeId,
            ["contentHash"] = embedding.ContentHash,
            ["provider"] = embedding.Provider,
            ["model"] = embedding.Model,
            ["dimensions"] = embedding.Dimensions,
            ["metadataJson"] = JsonSerializer.Serialize(embedding.Metadata)
        };

        foreach (var (key, value) in embedding.Metadata)
        {
            payload.TryAdd(key, value);
        }

        return payload;
    }

    private static SearchFilter? BuildFilter(IReadOnlyDictionary<string, string>? filters)
    {
        if (filters is null || filters.Count == 0)
        {
            return null;
        }

        return new SearchFilter(
            filters.Select(filter => new SearchCondition(
                filter.Key,
                new MatchValue(filter.Value))).ToArray());
    }

    private static string PayloadString(IReadOnlyDictionary<string, JsonElement> payload, string key)
    {
        return PayloadNullableString(payload, key) ?? string.Empty;
    }

    private static string? PayloadNullableString(IReadOnlyDictionary<string, JsonElement> payload, string key)
    {
        if (!payload.TryGetValue(key, out var value))
        {
            return null;
        }

        return value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : value.ToString();
    }

    private static IReadOnlyDictionary<string, string> PayloadMetadata(IReadOnlyDictionary<string, JsonElement> payload)
    {
        if (payload.TryGetValue("metadataJson", out var metadataJson) &&
            metadataJson.ValueKind == JsonValueKind.String)
        {
            var metadata = JsonSerializer.Deserialize<Dictionary<string, string>>(metadataJson.GetString() ?? string.Empty);
            if (metadata is not null)
            {
                return metadata;
            }
        }

        return new Dictionary<string, string>();
    }

    private sealed record CreateCollectionRequest(
        [property: JsonPropertyName("vectors")] VectorParams Vectors);

    private sealed record VectorParams(
        [property: JsonPropertyName("size")] int Size,
        [property: JsonPropertyName("distance")] string Distance);

    private sealed record UpsertRequest(
        [property: JsonPropertyName("points")] IReadOnlyList<PointStruct> Points);

    private sealed record PointStruct(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("vector")] IReadOnlyList<float> Vector,
        [property: JsonPropertyName("payload")] IReadOnlyDictionary<string, object> Payload);

    private sealed record SearchRequest(
        [property: JsonPropertyName("vector")] IReadOnlyList<float> Vector,
        [property: JsonPropertyName("limit")] int Limit,
        [property: JsonPropertyName("with_payload")] bool WithPayload,
        [property: JsonPropertyName("filter")] SearchFilter? Filter);

    private sealed record SearchFilter(
        [property: JsonPropertyName("must")] IReadOnlyList<SearchCondition> Must);

    private sealed record SearchCondition(
        [property: JsonPropertyName("key")] string Key,
        [property: JsonPropertyName("match")] MatchValue Match);

    private sealed record MatchValue(
        [property: JsonPropertyName("value")] string Value);

    private sealed record SearchResponse(
        [property: JsonPropertyName("result")] IReadOnlyList<SearchResult> Result);

    private sealed record SearchResult(
        [property: JsonPropertyName("score")] double Score,
        [property: JsonPropertyName("payload")] Dictionary<string, JsonElement> Payload);
}
