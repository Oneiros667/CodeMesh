namespace CodeMesh.Control.Configuration;

public static class CodeMeshIngestPathResolver
{
    public static string? ResolveFile(string repositoryRoot, string? path, string optionName)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return null;
        }

        var root = Path.GetFullPath(repositoryRoot);
        var rootRelativeCandidate = Path.GetFullPath(path, root);
        if (File.Exists(rootRelativeCandidate))
        {
            return rootRelativeCandidate;
        }

        var callerRelativeCandidate = Path.GetFullPath(path);
        if (File.Exists(callerRelativeCandidate))
        {
            return callerRelativeCandidate;
        }

        throw new InvalidOperationException(
            $"{optionName} file not found relative to the repository root or current directory: {path}");
    }
}
