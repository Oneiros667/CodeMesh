using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace CodeMesh.Ingestion.Summary;

public sealed record OllamaCodeSummaryProviderOptions(
    string BaseUrl = "http://127.0.0.1:11434",
    string Model = "qwen2.5-coder:14b",
    TimeSpan? Timeout = null);

public sealed class OllamaCodeSummaryProvider : ICodeSummaryProvider, IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly HttpClient _http;
    private readonly bool _ownsHttpClient;

    public OllamaCodeSummaryProvider(OllamaCodeSummaryProviderOptions options)
        : this(CreateHttpClient(options), options.Model, ownsHttpClient: true)
    {
    }

    public OllamaCodeSummaryProvider(
        HttpClient httpClient,
        string model = "qwen2.5-coder:14b",
        bool ownsHttpClient = false)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(model);

        _http = httpClient;
        _ownsHttpClient = ownsHttpClient;
        Model = model;
    }

    public string Provider => "ollama";

    public string Model { get; }

    public async Task<CodeSummaryResult> SummarizeAsync(
        CodeSummaryRequest request,
        CancellationToken cancellationToken = default)
    {
        var messages = SummaryPrompt.CreateMessages(request);
        using var response = await _http
            .PostAsJsonAsync(
                "api/chat",
                new ChatRequest(
                    Model,
                    messages,
                    Stream: false,
                    Format: "json",
                    Options: new ChatOptions(Temperature: 0.1, NumPredict: 220)),
                JsonOptions,
                cancellationToken)
            .ConfigureAwait(false);

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
            throw new InvalidOperationException(
                $"Ollama summary request failed with HTTP {(int)response.StatusCode}: {body}");
        }

        var result = await response.Content
            .ReadFromJsonAsync<ChatResponse>(JsonOptions, cancellationToken)
            .ConfigureAwait(false);

        return SummaryPrompt.ParseResult(result?.Message.Content);
    }

    public void Dispose()
    {
        if (_ownsHttpClient)
        {
            _http.Dispose();
        }
    }

    private static HttpClient CreateHttpClient(OllamaCodeSummaryProviderOptions options)
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

    private sealed record ChatRequest(
        [property: JsonPropertyName("model")] string Model,
        [property: JsonPropertyName("messages")] IReadOnlyList<SummaryChatMessage> Messages,
        [property: JsonPropertyName("stream")] bool Stream,
        [property: JsonPropertyName("format")] string Format,
        [property: JsonPropertyName("options")] ChatOptions Options);

    private sealed record ChatOptions(
        [property: JsonPropertyName("temperature")] double Temperature,
        [property: JsonPropertyName("num_predict")] int NumPredict);

    private sealed record ChatResponse(
        [property: JsonPropertyName("message")] ChatResponseMessage Message);

    private sealed record ChatResponseMessage(
        [property: JsonPropertyName("content")] string Content);
}
