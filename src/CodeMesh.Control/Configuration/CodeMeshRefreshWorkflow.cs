namespace CodeMesh.Control.Configuration;

public sealed record CodeMeshRefreshTarget(string RootPath, string? SolutionPath);

public static class CodeMeshRefreshWorkflow
{
    public static CodeMeshRefreshTarget ResolveTarget(
        string? startPath = null,
        string? solutionPath = null,
        string? projectPath = null,
        string? language = null)
    {
        var rootPath = FindRepositoryRoot(startPath);
        var solution = ResolveSolutionPath(rootPath, solutionPath, projectPath, language);

        return new CodeMeshRefreshTarget(rootPath, solution);
    }

    public static string[] BuildRefreshIngestArgs(string[] args, CodeMeshRefreshTarget target)
    {
        var normalized = new List<string> { "ingest" };
        var skipNext = false;

        for (var index = 0; index < args.Length; index++)
        {
            if (skipNext)
            {
                skipNext = false;
                continue;
            }

            var arg = args[index];
            if (index == 0 && string.Equals(arg, "refresh", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (IsOptionWithValue(arg, "--root", "--repository-root", "--solution", "--solution-path"))
            {
                skipNext = true;
                continue;
            }

            normalized.Add(arg);
        }

        normalized.Add("--root");
        normalized.Add(target.RootPath);

        if (!string.IsNullOrWhiteSpace(target.SolutionPath))
        {
            normalized.Add("--solution");
            normalized.Add(target.SolutionPath);
        }

        return normalized.ToArray();
    }

    private static string? ResolveSolutionPath(
        string rootPath,
        string? solutionPath,
        string? projectPath,
        string? language)
    {
        if (!string.IsNullOrWhiteSpace(solutionPath))
        {
            var fullSolutionPath = Path.GetFullPath(solutionPath);
            if (!File.Exists(fullSolutionPath))
            {
                throw new InvalidOperationException($"Solution file not found: {fullSolutionPath}");
            }

            return fullSolutionPath;
        }

        if (!string.IsNullOrWhiteSpace(projectPath) || !IsCSharpLanguage(language))
        {
            return null;
        }

        return FindDefaultSolution(rootPath);
    }

    private static string FindRepositoryRoot(string? startPath)
    {
        var candidate = string.IsNullOrWhiteSpace(startPath)
            ? Directory.GetCurrentDirectory()
            : startPath;
        var fullPath = Path.GetFullPath(candidate);
        var directory = File.Exists(fullPath)
            ? new DirectoryInfo(Path.GetDirectoryName(fullPath) ?? fullPath)
            : new DirectoryInfo(fullPath);

        while (directory is not null)
        {
            if (IsRepositoryRoot(directory.FullName))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        return fullPath;
    }

    private static bool IsRepositoryRoot(string path)
    {
        return Directory.Exists(Path.Combine(path, ".git")) ||
            File.Exists(Path.Combine(path, CodeMeshSelfWorkflow.MarkerFileName)) ||
            File.Exists(Path.Combine(path, CodeMeshSelfWorkflow.SolutionFileName)) ||
            Directory.EnumerateFiles(path, "*.sln", SearchOption.TopDirectoryOnly).Any() ||
            Directory.EnumerateFiles(path, "*.slnx", SearchOption.TopDirectoryOnly).Any();
    }

    private static string? FindDefaultSolution(string rootPath)
    {
        var codeMeshSolution = Path.Combine(rootPath, CodeMeshSelfWorkflow.SolutionFileName);
        if (File.Exists(codeMeshSolution))
        {
            return codeMeshSolution;
        }

        var solutions = Directory
            .EnumerateFiles(rootPath, "*.sln", SearchOption.TopDirectoryOnly)
            .Concat(Directory.EnumerateFiles(rootPath, "*.slnx", SearchOption.TopDirectoryOnly))
            .ToArray();

        return solutions.Length == 1 ? solutions[0] : null;
    }

    private static bool IsCSharpLanguage(string? language)
    {
        if (string.IsNullOrWhiteSpace(language))
        {
            return true;
        }

        return language.Trim().ToLowerInvariant() is "csharp" or "cs" or "c#";
    }

    private static bool IsOptionWithValue(string arg, params string[] names)
    {
        return names.Any(name => string.Equals(arg, name, StringComparison.OrdinalIgnoreCase));
    }
}
