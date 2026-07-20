namespace CodeMesh.Tests.Fixtures;

internal static class CodeMeshEvaluationCanary
{
    // Deliberately fake value used to verify that live MCP reports never expose redacted content.
    public const string ExampleConfiguration = "CODEMESH_EVAL_TOKEN=cm_eval_not_a_real_secret_7f93d2";
}
