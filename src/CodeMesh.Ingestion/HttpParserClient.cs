using System.Net.Http.Json;
using CodeMesh.Domain.Contracts;

namespace CodeMesh.Ingestion;

public sealed class HttpParserClient(HttpClient httpClient) : IParserClient
{
    public async Task<ParserCapability> GetCapabilityAsync(CancellationToken cancellationToken = default)
    {
        var capability = await httpClient.GetFromJsonAsync<ParserCapability>(
            "capabilities",
            cancellationToken).ConfigureAwait(false);

        return capability ?? throw new InvalidOperationException("Parser worker returned an empty capability response.");
    }

    public async Task<ParseResult> ParseAsync(ParseRequest request, CancellationToken cancellationToken = default)
    {
        using var response = await httpClient.PostAsJsonAsync(
            "parse",
            request,
            cancellationToken).ConfigureAwait(false);

        response.EnsureSuccessStatusCode();

        var result = await response.Content.ReadFromJsonAsync<ParseResult>(
            cancellationToken).ConfigureAwait(false);

        return result ?? throw new InvalidOperationException("Parser worker returned an empty parse response.");
    }
}
