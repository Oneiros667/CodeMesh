using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace CodeMesh.Ingestion.Summary;

public sealed record LmStudioCodeSummaryProviderOptions(
    string BaseUrl = "http://127.0.0.1:1234/v1",
    string Model = "qwen2.5-coder:14b",
    TimeSpan? Timeout = null);

public sealed class LmStudioCodeSummaryProvider : ICodeSummaryProvider, IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly HttpClient _http;
    private readonly bool _ownsHttpClient;

    public LmStudioCodeSummaryProvider(LmStudioCodeSummaryProviderOptions options)
        : this(CreateHttpClient(options), options.Model, ownsHttpClient: true)
    {
    }

    public LmStudioCodeSummaryProvider(
        HttpClient httpClient,
        string model = "qwen2.5-coder:14b",
        bool ownsHttpClient = false)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(model);

        _http = httpClient;
        _ownsHttpClient = ownsHttpClient;
        Model = model;
    }

    public string Provider => "lmstudio";

    public string Model { get; }

    public async Task<CodeSummaryResult> SummarizeAsync(
        CodeSummaryRequest request,
        CancellationToken cancellationToken = default)
    {
        var messages = SummaryPrompt.CreateMessages(request);
        using var response = await _http
            .PostAsJsonAsync(
                "chat/completions",
                new ChatCompletionRequest(
                    Model,
                    messages,
                    Temperature: 0.1,
                    MaxTokens: 220,
                    ResponseFormat: new ResponseFormat("text")),
                JsonOptions,
                cancellationToken)
            .ConfigureAwait(false);

        if (!response.IsSuccessStatusCode)
        {
            var body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);
            throw new InvalidOperationException(
                $"LM Studio summary request failed with HTTP {(int)response.StatusCode}: {body}");
        }

        var result = await response.Content
            .ReadFromJsonAsync<ChatCompletionResponse>(JsonOptions, cancellationToken)
            .ConfigureAwait(false);
        var content = result?.Choices.FirstOrDefault()?.Message.Content;

        return SummaryPrompt.ParseResult(content);
    }

    public void Dispose()
    {
        if (_ownsHttpClient)
        {
            _http.Dispose();
        }
    }

    private static HttpClient CreateHttpClient(LmStudioCodeSummaryProviderOptions options)
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

    private sealed record ChatCompletionRequest(
        [property: JsonPropertyName("model")] string Model,
        [property: JsonPropertyName("messages")] IReadOnlyList<SummaryChatMessage> Messages,
        [property: JsonPropertyName("temperature")] double Temperature,
        [property: JsonPropertyName("max_tokens")] int MaxTokens,
        [property: JsonPropertyName("response_format")] ResponseFormat ResponseFormat);

    private sealed record ResponseFormat(
        [property: JsonPropertyName("type")] string Type);

    private sealed record ChatCompletionResponse(
        [property: JsonPropertyName("choices")] IReadOnlyList<ChatChoice> Choices);

    private sealed record ChatChoice(
        [property: JsonPropertyName("message")] ChatChoiceMessage Message);

    private sealed record ChatChoiceMessage(
        [property: JsonPropertyName("content")] string Content);
}
