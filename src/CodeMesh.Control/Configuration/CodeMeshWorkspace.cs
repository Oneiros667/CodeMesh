namespace CodeMesh.Control.Configuration;

public sealed record CodeMeshWorkspace(
    string RootPath,
    string ConfigPath,
    string ComposePath,
    string EnvExamplePath,
    string AgentAccessPath)
{
    public static CodeMeshWorkspace Discover(string? startPath = null)
    {
        var start = Path.GetFullPath(startPath ?? Directory.GetCurrentDirectory());
        var directory = new DirectoryInfo(File.Exists(start) ? Path.GetDirectoryName(start)! : start);

        while (directory is not null)
        {
            var configPath = Path.Combine(directory.FullName, "codemesh.yaml");
            var solutionPath = Path.Combine(directory.FullName, "CodeMesh.sln");

            if (File.Exists(configPath) || File.Exists(solutionPath))
            {
                return FromRoot(directory.FullName);
            }

            directory = directory.Parent;
        }

        return FromRoot(start);
    }

    public static CodeMeshWorkspace FromRoot(string rootPath)
    {
        var root = Path.GetFullPath(rootPath);
        return new CodeMeshWorkspace(
            root,
            Path.Combine(root, "codemesh.yaml"),
            Path.Combine(root, "docker-compose.yml"),
            Path.Combine(root, ".env.example"),
            Path.Combine(root, "agent-access"));
    }
}
