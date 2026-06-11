namespace CodeMesh.Control.Configuration;

public sealed record CodeMeshSelfTarget(string RootPath, string SolutionPath);

public static class CodeMeshSelfWorkflow
{
    public const string SolutionFileName = "CodeMesh.sln";
    public const string MarkerFileName = "codemesh.yaml";
    public const string AgentInstructionsFileName = "Agents.md";

    public static CodeMeshSelfTarget ResolveTarget(string? startPath = null, string? solutionPath = null)
    {
        var root = FindRepositoryRoot(startPath);
        var solution = string.IsNullOrWhiteSpace(solutionPath)
            ? Path.Combine(root, SolutionFileName)
            : Path.GetFullPath(solutionPath);

        if (!File.Exists(solution))
        {
            throw new InvalidOperationException($"CodeMesh solution file not found: {solution}");
        }

        return new CodeMeshSelfTarget(root, solution);
    }

    public static string FindRepositoryRoot(string? startPath = null)
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
            if (IsCodeMeshRoot(directory.FullName))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new InvalidOperationException(
            $"Could not find a CodeMesh repository root from '{fullPath}'. Expected {SolutionFileName} and {MarkerFileName} or {AgentInstructionsFileName}.");
    }

    public static string[] BuildSelfIngestArgs(string[] args, CodeMeshSelfTarget target)
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
            if (index == 0 && string.Equals(arg, "self", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (index == 1 && IsSelfSubcommand(arg))
            {
                continue;
            }

            if (IsOptionWithValue(arg, "--root", "--repository-root", "--solution", "--solution-path", "--agent-access-url", "--agent-timeout-seconds", "--query", "--limit"))
            {
                skipNext = true;
                continue;
            }

            normalized.Add(arg);
        }

        normalized.Add("--root");
        normalized.Add(target.RootPath);
        normalized.Add("--solution");
        normalized.Add(target.SolutionPath);

        return normalized.ToArray();
    }

    private static bool IsCodeMeshRoot(string path)
    {
        return File.Exists(Path.Combine(path, SolutionFileName)) &&
            (File.Exists(Path.Combine(path, MarkerFileName)) ||
             File.Exists(Path.Combine(path, AgentInstructionsFileName)));
    }

    private static bool IsOptionWithValue(string arg, params string[] names)
    {
        return names.Any(name => string.Equals(arg, name, StringComparison.OrdinalIgnoreCase));
    }

    private static bool IsSelfSubcommand(string arg)
    {
        return string.Equals(arg, "ingest", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(arg, "smoke", StringComparison.OrdinalIgnoreCase);
    }
}
