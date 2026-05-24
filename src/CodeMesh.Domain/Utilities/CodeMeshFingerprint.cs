using CodeMesh.Domain.Graph;

namespace CodeMesh.Domain.Utilities;

public static class CodeMeshFingerprint
{
    private static readonly HashSet<string> RuntimeMetadataKeys = new(StringComparer.Ordinal)
    {
        "repositoryId",
        "repositoryRoot",
        "repositoryRemoteUrl",
        "repositoryBranch",
        "repositoryCommit",
        "ingestionRunId",
        "lastSeenAt"
    };

    public static string ForNode(CodeNode node)
    {
        return CodeMeshHash.StableId(
            node.Id,
            node.StableKey,
            node.Kind.ToString(),
            node.Name,
            node.Language,
            node.Project,
            node.Span.FilePath,
            node.Span.StartLine.ToString(),
            node.Span.StartColumn.ToString(),
            node.Span.EndLine.ToString(),
            node.Span.EndColumn.ToString(),
            node.ContentHash,
            StableMetadata(node.Metadata));
    }

    public static string ForRelationship(CodeRelationship relationship)
    {
        return CodeMeshHash.StableId(
            relationship.Id,
            relationship.SourceNodeId,
            relationship.TargetNodeId,
            relationship.Kind.ToString(),
            relationship.Label,
            StableMetadata(relationship.Metadata));
    }

    private static string StableMetadata(IReadOnlyDictionary<string, string> metadata)
    {
        if (metadata.Count == 0)
        {
            return string.Empty;
        }

        return string.Join(
            '\u001e',
            metadata
                .Where(item => !RuntimeMetadataKeys.Contains(item.Key))
                .OrderBy(item => item.Key, StringComparer.Ordinal)
                .Select(item => $"{item.Key}\u001d{item.Value}"));
    }
}
