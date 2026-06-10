using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Ingestion.Embedding;

public sealed record OllamaEmbeddingProviderOptions(
    string BaseUrl = "http://127.0.0.1:11434",
    string Model = "nomic-embed-text-v2-moe:latest",
    int BatchSize = 16,
    int MaxInputCharacters = 1500,
    TimeSpan? Timeout = null);

public sealed class OllamaEmbeddingProvider : IEmbeddingProvider, IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly HttpClient _http;
    private readonly bool _ownsHttpClient;
    private readonly int _batchSize;
    private readonly int _maxInputCharacters;

    public OllamaEmbeddingProvider(OllamaEmbeddingProviderOptions options)
        : this(CreateHttpClient(options), options.Model, options.BatchSize, options.MaxInputCharacters, ownsHttpClient: true)
    {
    }

    public OllamaEmbeddingProvider(
        HttpClient httpClient,
        string model = "nomic-embed-text-v2-moe:latest",
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

    public string Provider => "ollama";

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
                    $"Ollama returned {vectors.Count} embedding(s) for a batch of {batch.Length} input(s).");
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
            .PostAsJsonAsync("api/embed", new EmbedRequest(Model, inputs), JsonOptions, cancellationToken)
            .ConfigureAwait(false);

        if (response.StatusCode is HttpStatusCode.NotFound or HttpStatusCode.MethodNotAllowed)
        {
            return await EmbedLegacyBatchAsync(inputs, cancellationToken).ConfigureAwait(false);
        }

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
            throw new InvalidOperationException(
                $"Ollama embedding request failed with HTTP {(int)response.StatusCode}: {body}");
        }

        var result = await response.Content
            .ReadFromJsonAsync<EmbedResponse>(JsonOptions, cancellationToken)
            .ConfigureAwait(false);

        return result?.Embeddings ?? Array.Empty<IReadOnlyList<float>>();
    }

    private async Task<IReadOnlyList<IReadOnlyList<float>>> EmbedLegacyBatchAsync(
        IReadOnlyList<string> inputs,
        CancellationToken cancellationToken)
    {
        var vectors = new List<IReadOnlyList<float>>(inputs.Count);
        foreach (var input in inputs)
        {
            using var response = await _http
                .PostAsJsonAsync("api/embeddings", new LegacyEmbeddingRequest(Model, input), JsonOptions, cancellationToken)
                .ConfigureAwait(false);

            if (!response.IsSuccessStatusCode)
            {
                var body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
                throw new InvalidOperationException(
                    $"Ollama legacy embedding request failed with HTTP {(int)response.StatusCode}: {body}");
            }

            var result = await response.Content
                .ReadFromJsonAsync<LegacyEmbeddingResponse>(JsonOptions, cancellationToken)
                .ConfigureAwait(false);

            vectors.Add(result?.Embedding ?? Array.Empty<float>());
        }

        return vectors;
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

        text = $"search_document: {text}";

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

    private static HttpClient CreateHttpClient(OllamaEmbeddingProviderOptions options)
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

    private sealed record EmbedRequest(
        [property: JsonPropertyName("model")] string Model,
        [property: JsonPropertyName("input")] IReadOnlyList<string> Input);

    private sealed record EmbedResponse(
        [property: JsonPropertyName("embeddings")] IReadOnlyList<IReadOnlyList<float>> Embeddings);

    private sealed record LegacyEmbeddingRequest(
        [property: JsonPropertyName("model")] string Model,
        [property: JsonPropertyName("prompt")] string Prompt);

    private sealed record LegacyEmbeddingResponse(
        [property: JsonPropertyName("embedding")] IReadOnlyList<float> Embedding);
}
