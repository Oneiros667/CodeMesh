namespace CodeMesh.Control.Configuration;

public sealed record CodeMeshWatchSnapshot(IReadOnlyDictionary<string, string> Files);

public static class CodeMeshWatchWorkflow
{
    private static readonly HashSet<string> IgnoredDirectories = new(StringComparer.OrdinalIgnoreCase)
    {
        ".git",
        ".idea",
        ".vs",
        ".venv",
        ".pytest_cache",
        ".ruff_cache",
        "bin",
        "build",
        "dist",
        "node_modules",
        "obj"
    };

    public static string[] BuildWatchRefreshArgs(string[] args, CodeMeshRefreshTarget target)
    {
        var refreshArgs = new List<string> { "refresh" };
        var skipNext = false;

        for (var index = 0; index < args.Length; index++)
        {
            if (skipNext)
            {
                skipNext = false;
                continue;
            }

            var arg = args[index];
            if (index == 0 && string.Equals(arg, "watch", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (IsWatchOptionWithValue(arg))
            {
                skipNext = true;
                continue;
            }

            if (IsWatchFlag(arg))
            {
                continue;
            }

            refreshArgs.Add(arg);
        }

        return CodeMeshRefreshWorkflow.BuildRefreshIngestArgs(refreshArgs.ToArray(), target);
    }

    public static CodeMeshWatchSnapshot CreateSnapshot(string rootPath)
    {
        var files = new SortedDictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var file in EnumerateFiles(rootPath))
        {
            var info = new FileInfo(file);
            var relativePath = Path.GetRelativePath(rootPath, file);
            files[relativePath] = $"{info.Length}:{info.LastWriteTimeUtc.Ticks}";
        }

        return new CodeMeshWatchSnapshot(files);
    }

    public static bool HasChanges(CodeMeshWatchSnapshot previous, CodeMeshWatchSnapshot current)
    {
        if (previous.Files.Count != current.Files.Count)
        {
            return true;
        }

        foreach (var (path, fingerprint) in previous.Files)
        {
            if (!current.Files.TryGetValue(path, out var currentFingerprint) ||
                !string.Equals(fingerprint, currentFingerprint, StringComparison.Ordinal))
            {
                return true;
            }
        }

        return false;
    }

    private static IEnumerable<string> EnumerateFiles(string rootPath)
    {
        var pending = new Stack<string>();
        pending.Push(rootPath);

        while (pending.Count > 0)
        {
            var directory = pending.Pop();

            foreach (var child in Directory.EnumerateDirectories(directory))
            {
                if (!IgnoredDirectories.Contains(Path.GetFileName(child)))
                {
                    pending.Push(child);
                }
            }

            foreach (var file in Directory.EnumerateFiles(directory))
            {
                yield return file;
            }
        }
    }

    private static bool IsWatchOptionWithValue(string arg)
    {
        return string.Equals(arg, "--poll-seconds", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(arg, "--max-runs", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsWatchFlag(string arg)
    {
        return string.Equals(arg, "--run-once", StringComparison.OrdinalIgnoreCase);
    }
}
