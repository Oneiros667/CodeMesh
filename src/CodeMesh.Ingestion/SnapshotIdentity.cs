using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Ingestion;

internal sealed record ComputedSnapshotIdentity(
    string SnapshotId,
    string SourceViewHash,
    string ScopeFingerprint,
    string ParserProfileFingerprint,
    string GraphSchemaVersion);

internal static class SnapshotIdentity
{
    public const string IdentityFormatVersion = "snapshot-identity-v1";
    public const string GraphSchemaVersion = "codemesh-graph-v1";
    public const string RedactionProfileVersion = "content-redaction-v1";

    public static ComputedSnapshotIdentity Compute(
        string projectId,
        IngestionRequest request,
        ParseResult parseResult,
        IReadOnlyList<CodeNode> nodes,
        IReadOnlyList<CodeRelationship> relationships,
        IReadOnlyList<CodeContent> contents)
    {
        var sourceViewHash = CodeMeshHash.Sha256Hex(string.Join(
            '\n',
            nodes.Select(node => $"N\u001f{node.StableKey}\u001f{node.Span.FilePath}\u001f{node.ContentHash}\u001f{CodeMeshFingerprint.ForNode(node)}")
                .Concat(relationships.Select(relationship => $"R\u001f{relationship.Id}\u001f{CodeMeshFingerprint.ForRelationship(relationship)}"))
                .Concat(contents.Select(content => $"C\u001f{content.Hash}"))
                .OrderBy(value => value, StringComparer.Ordinal)));
        var scopeFingerprint = CodeMeshHash.StableId(
            request.Language,
            NormalizeScopePath(request.RepositoryRoot, request.SolutionPath),
            NormalizeScopePath(request.RepositoryRoot, request.ProjectPath),
            StableOptions(request.Options));
        var parserProfileFingerprint = CodeMeshHash.StableId(
            parseResult.ParserName,
            parseResult.Language,
            RedactionProfileVersion);
        var snapshotId = $"snp_{CodeMeshHash.StableId(
            IdentityFormatVersion,
            projectId,
            sourceViewHash,
            scopeFingerprint,
            parserProfileFingerprint,
            GraphSchemaVersion)}";

        return new ComputedSnapshotIdentity(
            snapshotId,
            sourceViewHash,
            scopeFingerprint,
            parserProfileFingerprint,
            GraphSchemaVersion);
    }

    private static string NormalizeScopePath(string repositoryRoot, string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return string.Empty;
        }

        var fullRoot = Path.GetFullPath(repositoryRoot);
        var fullPath = Path.IsPathRooted(path)
            ? Path.GetFullPath(path)
            : Path.GetFullPath(path, fullRoot);
        return Path.GetRelativePath(fullRoot, fullPath).Replace('\\', '/');
    }

    private static string StableOptions(IReadOnlyDictionary<string, string>? options)
    {
        return options is null
            ? string.Empty
            : string.Join('\u001e', options.OrderBy(item => item.Key, StringComparer.Ordinal).Select(item => $"{item.Key}\u001d{item.Value}"));
    }
}
