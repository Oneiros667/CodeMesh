using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Ingestion.Embedding;

public sealed record LmStudioEmbeddingProviderOptions(
    string BaseUrl = "http://127.0.0.1:1234/v1",
    string Model = "text-embedding-nomic-embed-text-v1.5",
    int BatchSize = 16,
    int MaxInputCharacters = 1500,
    TimeSpan? Timeout = null);

public sealed class LmStudioEmbeddingProvider : IEmbeddingProvider, IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly HttpClient _http;
    private readonly bool _ownsHttpClient;
    private readonly int _batchSize;
    private readonly int _maxInputCharacters;

    public LmStudioEmbeddingProvider(LmStudioEmbeddingProviderOptions options)
        : this(CreateHttpClient(options), options.Model, options.BatchSize, options.MaxInputCharacters, ownsHttpClient: true)
    {
    }

    public LmStudioEmbeddingProvider(
        HttpClient httpClient,
        string model = "text-embedding-nomic-embed-text-v1.5",
        int batchSize = 16,
        int maxInputCharacters = 1500,
        bool ownsHttpClient = false)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(model);

        _http = httpClient;
        _ownsHttpClient = ownsHttpClient;
        _batchSize = Math.Max(1, batchSize);
        _maxInputCharacters = Math.Max(256, maxInputCharacters);
        Model = model;
    }

    public string Provider => "lmstudio";

    public string Model { get; }

    public async Task<IReadOnlyList<EmbeddingRecord>> EmbedAsync(
        IReadOnlyList<CodeNode> nodes,
        IReadOnlyDictionary<string, CodeContent> contentByHash,
        CancellationToken cancellationToken = default)
    {
        var inputs = nodes
            .Select(node => CreateInput(node, contentByHash))
            .Where(input => !string.IsNullOrWhiteSpace(input.Text))
            .ToArray();

        if (inputs.Length == 0)
        {
            return Array.Empty<EmbeddingRecord>();
        }

        var records = new List<EmbeddingRecord>(inputs.Length);
        foreach (var batch in inputs.Chunk(_batchSize))
        {
            cancellationToken.ThrowIfCancellationRequested();

            var vectors = await EmbedBatchAsync(
                batch.Select(input => input.Text).ToArray(),
                cancellationToken).ConfigureAwait(false);

            if (vectors.Count != batch.Length)
            {
                throw new InvalidOperationException(
                    $"LM Studio returned {vectors.Count} embedding(s) for a batch of {batch.Length} input(s).");
            }

            for (var i = 0; i < batch.Length; i++)
            {
                var input = batch[i];
                var vector = vectors[i];
                records.Add(new EmbeddingRecord(
                    CodeMeshHash.StableId("embedding", Provider, Model, input.Node.Id, input.Node.ContentHash),
                    input.Node.Id,
                    input.Node.ContentHash,
                    Provider,
                    Model,
                    vector.Count,
                    vector,
                    MetadataFor(input.Node, input.Preview)));
            }
        }

        return records;
    }

    public void Dispose()
    {
        if (_ownsHttpClient)
        {
            _http.Dispose();
        }
    }

    private async Task<IReadOnlyList<IReadOnlyList<float>>> EmbedBatchAsync(
        IReadOnlyList<string> inputs,
        CancellationToken cancellationToken)
    {
        using var response = await _http
            .PostAsJsonAsync("embeddings", new EmbeddingRequest(Model, inputs), JsonOptions, cancellationToken)
            .ConfigureAwait(false);

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
            throw new InvalidOperationException(
                $"LM Studio embedding request failed with HTTP {(int)response.StatusCode}: {body}");
        }

        var result = await response.Content
            .ReadFromJsonAsync<EmbeddingResponse>(JsonOptions, cancellationToken)
            .ConfigureAwait(false);

        return (result?.Data ?? Array.Empty<EmbeddingData>())
            .OrderBy(item => item.Index)
            .Select(item => item.Embedding)
            .ToArray();
    }

    private EmbeddingInput CreateInput(
        CodeNode node,
        IReadOnlyDictionary<string, CodeContent> contentByHash)
    {
        var text = contentByHash.TryGetValue(node.ContentHash, out var content)
            ? content.Text
            : node.StableKey;
        var compact = text.ReplaceLineEndings(" ").Trim();
        var preview = compact.Length <= 180 ? compact : compact[..180];

        if (text.Length > _maxInputCharacters)
        {
            text = text[.._maxInputCharacters];
        }

        return new EmbeddingInput(node, text, preview);
    }

    private static IReadOnlyDictionary<string, string> MetadataFor(CodeNode node, string preview)
    {
        return new Dictionary<string, string>
        {
            ["preview"] = preview,
            ["kind"] = node.Kind.ToString(),
            ["name"] = node.Name,
            ["language"] = node.Language,
            ["project"] = node.Project,
            ["filePath"] = node.Span.FilePath,
            ["startLine"] = node.Span.StartLine.ToString(),
            ["endLine"] = node.Span.EndLine.ToString()
        };
    }

    private static HttpClient CreateHttpClient(LmStudioEmbeddingProviderOptions options)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(options.BaseUrl);

        var baseAddress = options.BaseUrl.EndsWith("/", StringComparison.Ordinal)
            ? options.BaseUrl
            : $"{options.BaseUrl}/";

        return new HttpClient
        {
            BaseAddress = new Uri(baseAddress, UriKind.Absolute),
            Timeout = options.Timeout ?? TimeSpan.FromMinutes(10)
        };
    }

    private sealed record EmbeddingInput(
        CodeNode Node,
        string Text,
        string Preview);

    private sealed record EmbeddingRequest(
        [property: JsonPropertyName("model")] string Model,
        [property: JsonPropertyName("input")] IReadOnlyList<string> Input);

    private sealed record EmbeddingResponse(
        [property: JsonPropertyName("data")] IReadOnlyList<EmbeddingData> Data);

    private sealed record EmbeddingData(
        [property: JsonPropertyName("embedding")] IReadOnlyList<float> Embedding,
        [property: JsonPropertyName("index")] int Index);
}
