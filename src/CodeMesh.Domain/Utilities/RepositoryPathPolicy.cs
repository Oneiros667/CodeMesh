namespace CodeMesh.Domain.Utilities;

public static class RepositoryPathPolicy
{
    private static readonly HashSet<string> IgnoredDirectoryNames = new(StringComparer.OrdinalIgnoreCase)
    {
        ".codemesh-live-summary",
        ".codemesh",
        ".codemesh-smoke",
        ".dotnet_home",
        ".git",
        ".idea",
        ".mypy_cache",
        ".nuget",
        ".pytest_cache",
        ".ruff_cache",
        ".tmp",
        ".tox",
        ".venv",
        ".vs",
        ".vscode",
        "__pycache__",
        "bin",
        "build",
        "dist",
        "node_modules",
        "obj",
        "target",
        "venv"
    };

    public static bool IsIgnoredPath(string repositoryRoot, string candidatePath)
    {
        return IsIgnoredRelativePath(Path.GetRelativePath(repositoryRoot, candidatePath));
    }

    public static bool IsIgnoredRelativePath(string relativePath)
    {
        return relativePath
            .Split(['/', '\\'], StringSplitOptions.RemoveEmptyEntries)
            .Any(IsIgnoredSegment);
    }

    private static bool IsIgnoredSegment(string segment)
    {
        return IgnoredDirectoryNames.Contains(segment) ||
            segment.EndsWith(".egg-info", StringComparison.OrdinalIgnoreCase);
    }
}
