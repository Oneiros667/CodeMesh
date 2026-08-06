using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Ingestion.Summary;

internal static class CodeSummaryIdentity
{
    public static bool IsCandidate(CodeNode node)
    {
        return node.Kind is
            CodeNodeKind.File or
            CodeNodeKind.TestFile or
            CodeNodeKind.Class or
            CodeNodeKind.Interface or
            CodeNodeKind.Struct or
            CodeNodeKind.Enum or
            CodeNodeKind.Delegate or
            CodeNodeKind.Method or
            CodeNodeKind.TestCase or
            CodeNodeKind.Constructor or
            CodeNodeKind.Property or
            CodeNodeKind.Event;
    }

    public static string SummaryKind(CodeNode node)
    {
        return node.Kind is CodeNodeKind.File or CodeNodeKind.TestFile ? "file" : "symbol";
    }

    public static string LookupKey(string nodeId, string contentHash, string summaryKind)
    {
        return $"{nodeId}\u001f{contentHash}\u001f{summaryKind}";
    }

    public static string SummaryId(
        string repositoryId,
        CodeNode node,
        string summaryKind,
        string provider,
        string model,
        string promptVersion,
        string generationConfigurationFingerprint)
    {
        return CodeMeshHash.StableId(
            "summary",
            repositoryId,
            node.Id,
            node.ContentHash,
            summaryKind,
            provider,
            model,
            promptVersion,
            generationConfigurationFingerprint);
    }
}
