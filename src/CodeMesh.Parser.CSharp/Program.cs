using CodeMesh.Domain.Contracts;
using CodeMesh.Parser.CSharp;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSingleton<CSharpParseService>();

var app = builder.Build();

app.MapGet("/health", () => Results.Ok(new
{
    service = "codemesh-parser-csharp",
    status = "healthy",
    checkedAt = DateTimeOffset.UtcNow
}));

app.MapGet("/capabilities", () => CSharpParseService.Capability);

app.MapPost("/parse", async (
    ParseRequest request,
    CSharpParseService parser,
    CancellationToken cancellationToken) =>
{
    var result = await parser.ParseAsync(request, cancellationToken).ConfigureAwait(false);
    return Results.Ok(result);
});

app.Run();
