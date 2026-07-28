using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace CodeMesh.Ingestion.Summary;

public sealed record OpenAiCodeSummaryProviderOptions(
    string ApiKey,
    string BaseUrl = "https://api.openai.com/v1",
    string Model = "gpt-5.6-luna",
    TimeSpan? Timeout = null);

public sealed class OpenAiCodeSummaryProvider : ICodeSummaryProvider, IDisposable
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);
    private static readonly JsonElement SummarySchema = JsonDocument.Parse(
        """
        {
          "type": "object",
          "properties": {
            "summary": {
              "type": "string"
            },
            "tags": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "maxItems": 8
            },
            "confidence": {
              "type": "string",
              "enum": ["high", "medium", "low"]
            }
          },
          "required": ["summary", "tags", "confidence"],
          "additionalProperties": false
        }
        """).RootElement.Clone();

    private readonly HttpClient _http;
    private readonly string _apiKey;
    private readonly bool _ownsHttpClient;

    public OpenAiCodeSummaryProvider(OpenAiCodeSummaryProviderOptions options)
        : this(
            CreateHttpClient(options),
            options.ApiKey,
            options.Model,
            ownsHttpClient: true)
    {
    }

    public OpenAiCodeSummaryProvider(
        HttpClient httpClient,
        string apiKey,
        string model = "gpt-5.6-luna",
        bool ownsHttpClient = false)
    {
        ArgumentNullException.ThrowIfNull(httpClient);
        ArgumentException.ThrowIfNullOrWhiteSpace(apiKey);
        ArgumentException.ThrowIfNullOrWhiteSpace(model);

        _http = httpClient;
        _apiKey = apiKey;
        _ownsHttpClient = ownsHttpClient;
        Model = model;
    }

    public string Provider => "openai";

    public string Model { get; }

    public async Task<CodeSummaryResult> SummarizeAsync(
        CodeSummaryRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        using var message = new HttpRequestMessage(HttpMethod.Post, "responses")
        {
            Content = JsonContent.Create(
                new ResponsesRequest(
                    Model,
                    SummaryPrompt.CreateMessages(request),
                    new ResponsesText(
                        new ResponsesFormat(
                            "json_schema",
                            "codemesh_node_summary",
                            Strict: true,
                            SummarySchema)),
                    request.Budget?.MaxCompletionTokens ?? 1024,
                    Store: false),
                options: JsonOptions)
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _apiKey);

        using var response = await _http
            .SendAsync(message, cancellationToken)
            .ConfigureAwait(false);
        var body = await response.Content.ReadAsStringAsync(cancellationToken).ConfigureAwait(false);

        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(
                $"OpenAI summary request failed with HTTP {(int)response.StatusCode}: {ReadErrorMessage(body)}");
        }

        ResponsesResponse? result;
        try
        {
            result = JsonSerializer.Deserialize<ResponsesResponse>(body, JsonOptions);
        }
        catch (JsonException exception)
        {
            throw new InvalidOperationException("OpenAI returned malformed response JSON.", exception);
        }

        if (result is null)
        {
            throw new InvalidOperationException("OpenAI returned an empty response.");
        }

        if (!string.Equals(result.Status, "completed", StringComparison.OrdinalIgnoreCase))
        {
            var reason = string.IsNullOrWhiteSpace(result.IncompleteDetails?.Reason)
                ? "unknown reason"
                : result.IncompleteDetails.Reason;
            throw new InvalidOperationException(
                $"OpenAI summary response did not complete: {reason}.");
        }

        var content = result.Output?
            .Where(item => string.Equals(item.Type, "message", StringComparison.OrdinalIgnoreCase))
            .SelectMany(item => item.Content ?? [])
            .ToArray() ?? [];
        if (content.Any(item => string.Equals(item.Type, "refusal", StringComparison.OrdinalIgnoreCase)))
        {
            throw new InvalidOperationException("OpenAI refused the summary request.");
        }

        var outputText = content
            .FirstOrDefault(item => string.Equals(item.Type, "output_text", StringComparison.OrdinalIgnoreCase))
            ?.Text;
        var summary = SummaryPrompt.ParseResult(outputText);
        return summary with
        {
            Usage = result.Usage is null
                ? null
                : new CodeSummaryUsage(
                    result.Usage.InputTokens,
                    result.Usage.InputTokenDetails?.CachedTokens ?? 0,
                    result.Usage.OutputTokens,
                    result.Usage.OutputTokenDetails?.ReasoningTokens ?? 0,
                    result.Usage.TotalTokens)
        };
    }

    public void Dispose()
    {
        if (_ownsHttpClient)
        {
            _http.Dispose();
        }
    }

    private static HttpClient CreateHttpClient(OpenAiCodeSummaryProviderOptions options)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(options.ApiKey);
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

    private static string ReadErrorMessage(string body)
    {
        try
        {
            using var document = JsonDocument.Parse(body);
            if (document.RootElement.TryGetProperty("error", out var error) &&
                error.TryGetProperty("message", out var message) &&
                message.ValueKind == JsonValueKind.String &&
                !string.IsNullOrWhiteSpace(message.GetString()))
            {
                return message.GetString()!;
            }
        }
        catch (JsonException)
        {
            // Fall through to the bounded message below. Do not echo arbitrary response bodies.
        }

        return "OpenAI returned an error response.";
    }

    private sealed record ResponsesRequest(
        [property: JsonPropertyName("model")] string Model,
        [property: JsonPropertyName("input")] IReadOnlyList<SummaryChatMessage> Input,
        [property: JsonPropertyName("text")] ResponsesText Text,
        [property: JsonPropertyName("max_output_tokens")] int MaxOutputTokens,
        [property: JsonPropertyName("store")] bool Store);

    private sealed record ResponsesText(
        [property: JsonPropertyName("format")] ResponsesFormat Format);

    private sealed record ResponsesFormat(
        [property: JsonPropertyName("type")] string Type,
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("strict")] bool Strict,
        [property: JsonPropertyName("schema")] JsonElement Schema);

    private sealed record ResponsesResponse(
        [property: JsonPropertyName("status")] string? Status,
        [property: JsonPropertyName("incomplete_details")] IncompleteDetails? IncompleteDetails,
        [property: JsonPropertyName("output")] IReadOnlyList<ResponseOutput>? Output,
        [property: JsonPropertyName("usage")] ResponseUsage? Usage);

    private sealed record IncompleteDetails(
        [property: JsonPropertyName("reason")] string? Reason);

    private sealed record ResponseOutput(
        [property: JsonPropertyName("type")] string? Type,
        [property: JsonPropertyName("content")] IReadOnlyList<ResponseContent>? Content);

    private sealed record ResponseContent(
        [property: JsonPropertyName("type")] string? Type,
        [property: JsonPropertyName("text")] string? Text);

    private sealed record ResponseUsage(
        [property: JsonPropertyName("input_tokens")] int InputTokens,
        [property: JsonPropertyName("input_tokens_details")] InputTokenDetails? InputTokenDetails,
        [property: JsonPropertyName("output_tokens")] int OutputTokens,
        [property: JsonPropertyName("output_tokens_details")] OutputTokenDetails? OutputTokenDetails,
        [property: JsonPropertyName("total_tokens")] int TotalTokens);

    private sealed record InputTokenDetails(
        [property: JsonPropertyName("cached_tokens")] int CachedTokens);

    private sealed record OutputTokenDetails(
        [property: JsonPropertyName("reasoning_tokens")] int ReasoningTokens);
}
