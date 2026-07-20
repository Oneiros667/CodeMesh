using System.Text.RegularExpressions;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Utilities;

namespace CodeMesh.Parser.Deployment;

public sealed partial class DeploymentParseService
{
    public static ParserCapability Capability { get; } = new(
        "codemesh-parser-deployment",
        "deployment",
        "0.1.0",
        ["Dockerfile", ".dockerfile", ".yml", ".yaml"],
        ["repositoryRoot"]);

    public async Task<ParseResult> ParseAsync(
        ParseRequest request,
        CancellationToken cancellationToken = default)
    {
        var repositoryRoot = Path.GetFullPath(request.RepositoryRoot);
        if (!Directory.Exists(repositoryRoot))
        {
            return Failure($"Repository root not found: {repositoryRoot}");
        }

        var nodes = new List<CodeNode>();
        var relationships = new List<CodeRelationship>();
        var contents = new List<CodeContent>();
        var diagnostics = new List<ParserDiagnostic>();
        var parsedAt = DateTimeOffset.UtcNow;

        foreach (var file in EnumerateDeploymentFiles(repositoryRoot))
        {
            cancellationToken.ThrowIfCancellationRequested();
            var relativePath = NormalizePath(Path.GetRelativePath(repositoryRoot, file));
            try
            {
                var text = await File.ReadAllTextAsync(file, cancellationToken).ConfigureAwait(false);
                if (IsDockerfile(file))
                {
                    ParseDockerfile(repositoryRoot, relativePath, text, parsedAt, nodes, relationships, contents);
                }
                else if (IsComposeFile(file))
                {
                    ParseComposeFile(repositoryRoot, relativePath, text, parsedAt, nodes, relationships, contents);
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                diagnostics.Add(new ParserDiagnostic(
                    "CMDEP001",
                    $"Could not read deployment file '{relativePath}': {exception.Message}",
                    "warning",
                    SourceSpan.Unknown(relativePath)));
            }
        }

        return new ParseResult(
            Capability.WorkerName,
            Capability.Language,
            nodes,
            relationships,
            contents,
            diagnostics,
            parsedAt);
    }

    private static void ParseDockerfile(
        string repositoryRoot,
        string relativePath,
        string text,
        DateTimeOffset parsedAt,
        List<CodeNode> nodes,
        List<CodeRelationship> relationships,
        List<CodeContent> contents)
    {
        var fileHash = CodeMeshHash.Sha256Hex(text);
        var fileNodeId = $"deployment:dockerfile:{relativePath}";
        nodes.Add(new CodeNode(
            fileNodeId,
            fileNodeId,
            CodeNodeKind.Dockerfile,
            Path.GetFileName(relativePath),
            "deployment",
            ProjectName(repositoryRoot),
            new SourceSpan(relativePath, 1, 1, Math.Max(1, CountLines(text)), 1),
            fileHash,
            new Dictionary<string, string>
            {
                ["filePath"] = relativePath,
                ["artifactType"] = "Dockerfile"
            }));
        contents.Add(new CodeContent(fileHash, text, "text/x-dockerfile", parsedAt, parsedAt));

        var lines = NormalizeLines(text);
        var stageStarts = DockerfileStages(lines).ToArray();
        for (var index = 0; index < stageStarts.Length; index++)
        {
            var stage = stageStarts[index];
            var endLine = index + 1 < stageStarts.Length
                ? stageStarts[index + 1].LineNumber - 1
                : lines.Length;
            var stageText = string.Join(Environment.NewLine, lines[(stage.LineNumber - 1)..endLine]);
            var stageHash = CodeMeshHash.Sha256Hex(stageText);
            var stageName = stage.Alias ?? $"stage-{index + 1}";
            var stageNodeId = $"deployment:dockerfile-stage:{relativePath}#{stageName}";
            var metadata = new Dictionary<string, string>
            {
                ["filePath"] = relativePath,
                ["artifactType"] = "DockerfileStage",
                ["baseImage"] = stage.BaseImage,
                ["stageIndex"] = index.ToString()
            };
            if (!string.IsNullOrWhiteSpace(stage.Alias))
            {
                metadata["stageAlias"] = stage.Alias;
            }

            AddDockerfileMetadata(lines[(stage.LineNumber - 1)..endLine], metadata);
            nodes.Add(new CodeNode(
                stageNodeId,
                stageNodeId,
                CodeNodeKind.DockerfileStage,
                stageName,
                "deployment",
                ProjectName(repositoryRoot),
                new SourceSpan(relativePath, stage.LineNumber, 1, Math.Max(stage.LineNumber, endLine), 1),
                stageHash,
                metadata));
            contents.Add(new CodeContent(stageHash, stageText, "text/x-dockerfile-fragment", parsedAt, parsedAt));
            relationships.Add(new CodeRelationship(
                CodeMeshHash.StableId("deployment", "contains", fileNodeId, stageNodeId),
                fileNodeId,
                stageNodeId,
                CodeRelationshipKind.Contains,
                null,
                new Dictionary<string, string> { ["filePath"] = relativePath }));
        }
    }

    private static void ParseComposeFile(
        string repositoryRoot,
        string relativePath,
        string text,
        DateTimeOffset parsedAt,
        List<CodeNode> nodes,
        List<CodeRelationship> relationships,
        List<CodeContent> contents)
    {
        var fileHash = CodeMeshHash.Sha256Hex(text);
        var fileNodeId = $"deployment:compose:{relativePath}";
        nodes.Add(new CodeNode(
            fileNodeId,
            fileNodeId,
            CodeNodeKind.ComposeFile,
            Path.GetFileName(relativePath),
            "deployment",
            ProjectName(repositoryRoot),
            new SourceSpan(relativePath, 1, 1, Math.Max(1, CountLines(text)), 1),
            fileHash,
            new Dictionary<string, string>
            {
                ["filePath"] = relativePath,
                ["artifactType"] = "DockerCompose"
            }));
        contents.Add(new CodeContent(fileHash, text, "application/x-yaml", parsedAt, parsedAt));

        var lines = NormalizeLines(text);
        var services = ComposeServices(lines).ToArray();
        var serviceNodeIds = services.ToDictionary(
            service => service.Name,
            service => $"deployment:compose-service:{relativePath}#{service.Name}",
            StringComparer.OrdinalIgnoreCase);

        foreach (var service in services)
        {
            var serviceText = string.Join(Environment.NewLine, lines[(service.LineNumber - 1)..service.EndLine]);
            var serviceHash = CodeMeshHash.Sha256Hex(serviceText);
            var nodeId = serviceNodeIds[service.Name];
            var block = lines[(service.LineNumber - 1)..service.EndLine];
            var metadata = ComposeServiceMetadata(block);
            metadata["filePath"] = relativePath;
            metadata["artifactType"] = "ComposeService";
            metadata["serviceName"] = service.Name;

            nodes.Add(new CodeNode(
                nodeId,
                nodeId,
                CodeNodeKind.ComposeService,
                service.Name,
                "deployment",
                ProjectName(repositoryRoot),
                new SourceSpan(relativePath, service.LineNumber, 1, Math.Max(service.LineNumber, service.EndLine), 1),
                serviceHash,
                metadata));
            contents.Add(new CodeContent(serviceHash, serviceText, "application/x-yaml-fragment", parsedAt, parsedAt));
            relationships.Add(new CodeRelationship(
                CodeMeshHash.StableId("deployment", "contains", fileNodeId, nodeId),
                fileNodeId,
                nodeId,
                CodeRelationshipKind.Contains,
                null,
                new Dictionary<string, string> { ["filePath"] = relativePath }));

            foreach (var dependency in Dependencies(block))
            {
                if (!serviceNodeIds.TryGetValue(dependency, out var targetNodeId))
                {
                    continue;
                }

                relationships.Add(new CodeRelationship(
                    CodeMeshHash.StableId("deployment", "depends-on", nodeId, targetNodeId),
                    nodeId,
                    targetNodeId,
                    CodeRelationshipKind.References,
                    "depends_on",
                    new Dictionary<string, string>
                    {
                        ["filePath"] = relativePath,
                        ["dependency"] = dependency
                    }));
            }
        }
    }

    private static IEnumerable<DockerfileStage> DockerfileStages(string[] lines)
    {
        for (var index = 0; index < lines.Length; index++)
        {
            var match = FromRegex().Match(lines[index]);
            if (!match.Success)
            {
                continue;
            }

            yield return new DockerfileStage(
                index + 1,
                match.Groups["image"].Value.Trim(),
                match.Groups["alias"].Success ? match.Groups["alias"].Value.Trim() : null);
        }
    }

    private static void AddDockerfileMetadata(string[] lines, Dictionary<string, string> metadata)
    {
        var expose = new List<string>();
        var env = new List<string>();
        var copyFrom = new List<string>();
        foreach (var line in lines)
        {
            var instruction = DockerInstructionRegex().Match(line);
            if (!instruction.Success)
            {
                continue;
            }

            var keyword = instruction.Groups["keyword"].Value.ToUpperInvariant();
            var value = instruction.Groups["value"].Value.Trim();
            switch (keyword)
            {
                case "EXPOSE":
                    expose.Add(value);
                    break;
                case "ENV":
                    env.Add(FirstToken(value).TrimEnd('='));
                    break;
                case "WORKDIR":
                    metadata["workdir"] = value;
                    break;
                case "ENTRYPOINT":
                    metadata["entrypoint"] = value;
                    break;
                case "CMD":
                    metadata["cmd"] = value;
                    break;
                case "COPY" when value.Contains("--from=", StringComparison.OrdinalIgnoreCase):
                    copyFrom.Add(value);
                    break;
            }
        }

        AddJoined(metadata, "exposedPorts", expose);
        AddJoined(metadata, "environmentKeys", env);
        AddJoined(metadata, "copyFrom", copyFrom);
    }

    private static IEnumerable<ComposeService> ComposeServices(string[] lines)
    {
        var servicesLine = Array.FindIndex(lines, line => ServicesRegex().IsMatch(line));
        if (servicesLine < 0)
        {
            yield break;
        }

        var serviceIndent = -1;
        var serviceStarts = new List<(string Name, int LineIndex, int Indent)>();
        for (var index = servicesLine + 1; index < lines.Length; index++)
        {
            var line = lines[index];
            if (string.IsNullOrWhiteSpace(line) || line.TrimStart().StartsWith('#'))
            {
                continue;
            }

            var indent = LeadingSpaces(line);
            if (indent == 0 && !line.StartsWith("services:", StringComparison.Ordinal))
            {
                break;
            }

            var match = MappingKeyRegex().Match(line);
            if (!match.Success)
            {
                continue;
            }

            if (serviceIndent < 0)
            {
                serviceIndent = indent;
            }

            if (indent == serviceIndent)
            {
                serviceStarts.Add((Unquote(match.Groups["key"].Value), index, indent));
            }
        }

        for (var index = 0; index < serviceStarts.Count; index++)
        {
            var current = serviceStarts[index];
            var endExclusive = index + 1 < serviceStarts.Count
                ? serviceStarts[index + 1].LineIndex
                : FindBlockEnd(lines, current.LineIndex, current.Indent);
            yield return new ComposeService(current.Name, current.LineIndex + 1, endExclusive);
        }
    }

    private static Dictionary<string, string> ComposeServiceMetadata(string[] block)
    {
        var metadata = new Dictionary<string, string>();
        var ports = ValuesUnderKey(block, "ports").ToArray();
        var environment = EnvironmentKeys(block).ToArray();
        var volumes = ValuesUnderKey(block, "volumes").ToArray();
        var dependsOn = Dependencies(block).ToArray();

        AddScalar(metadata, block, "image", "image");
        AddScalar(metadata, block, "build", "build");
        AddScalar(metadata, block, "dockerfile", "dockerfile");
        AddJoined(metadata, "ports", ports);
        AddJoined(metadata, "environmentKeys", environment);
        AddJoined(metadata, "volumes", volumes);
        AddJoined(metadata, "dependsOn", dependsOn);
        return metadata;
    }

    private static IEnumerable<string> Dependencies(string[] block)
    {
        return ValuesUnderKey(block, "depends_on")
            .Select(value => value.Split(':', 2)[0].Trim())
            .Where(value => !string.IsNullOrWhiteSpace(value));
    }

    private static IEnumerable<string> EnvironmentKeys(string[] block)
    {
        foreach (var value in ValuesUnderKey(block, "environment"))
        {
            var key = value.Split([':', '='], 2)[0].Trim();
            if (!string.IsNullOrWhiteSpace(key))
            {
                yield return key;
            }
        }
    }

    private static IEnumerable<string> ValuesUnderKey(string[] block, string key)
    {
        var keyLine = FindKeyLine(block, key);
        if (keyLine < 0)
        {
            yield break;
        }

        var baseIndent = LeadingSpaces(block[keyLine]);
        for (var index = keyLine + 1; index < block.Length; index++)
        {
            var line = block[index];
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var indent = LeadingSpaces(line);
            if (indent <= baseIndent)
            {
                yield break;
            }

            var trimmed = line.Trim();
            if (trimmed.StartsWith('-'))
            {
                var value = Unquote(trimmed[1..].Trim());
                if (!string.IsNullOrWhiteSpace(value))
                {
                    yield return value;
                }

                continue;
            }

            var match = MappingKeyRegex().Match(line);
            if (match.Success)
            {
                yield return Unquote(match.Groups["key"].Value);
            }
        }
    }

    private static void AddScalar(Dictionary<string, string> metadata, string[] block, string key, string metadataKey)
    {
        var lineIndex = FindKeyLine(block, key);
        if (lineIndex < 0)
        {
            return;
        }

        var match = MappingKeyRegex().Match(block[lineIndex]);
        var value = match.Groups["value"].Value.Trim();
        if (!string.IsNullOrWhiteSpace(value))
        {
            metadata[metadataKey] = Unquote(value);
        }
        else if (string.Equals(key, "build", StringComparison.OrdinalIgnoreCase))
        {
            var context = ScalarUnderKey(block, lineIndex, "context");
            if (!string.IsNullOrWhiteSpace(context))
            {
                metadata[metadataKey] = context;
            }
        }
    }

    private static string? ScalarUnderKey(string[] block, int parentLineIndex, string childKey)
    {
        var baseIndent = LeadingSpaces(block[parentLineIndex]);
        for (var index = parentLineIndex + 1; index < block.Length; index++)
        {
            var line = block[index];
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            if (LeadingSpaces(line) <= baseIndent)
            {
                return null;
            }

            var match = MappingKeyRegex().Match(line);
            if (match.Success && string.Equals(Unquote(match.Groups["key"].Value), childKey, StringComparison.OrdinalIgnoreCase))
            {
                return Unquote(match.Groups["value"].Value.Trim());
            }
        }

        return null;
    }

    private static int FindKeyLine(string[] block, string key)
    {
        for (var index = 0; index < block.Length; index++)
        {
            var match = MappingKeyRegex().Match(block[index]);
            if (match.Success && string.Equals(Unquote(match.Groups["key"].Value), key, StringComparison.OrdinalIgnoreCase))
            {
                return index;
            }
        }

        return -1;
    }

    private static int FindBlockEnd(string[] lines, int startIndex, int indent)
    {
        for (var index = startIndex + 1; index < lines.Length; index++)
        {
            var line = lines[index];
            if (string.IsNullOrWhiteSpace(line) || line.TrimStart().StartsWith('#'))
            {
                continue;
            }

            if (LeadingSpaces(line) <= indent)
            {
                return index;
            }
        }

        return lines.Length;
    }

    private static ParseResult Failure(string message)
    {
        return new ParseResult(
            Capability.WorkerName,
            Capability.Language,
            Array.Empty<CodeNode>(),
            Array.Empty<CodeRelationship>(),
            Array.Empty<CodeContent>(),
            [new ParserDiagnostic("CMDEP000", message, "error")],
            DateTimeOffset.UtcNow);
    }

    private static IEnumerable<string> EnumerateDeploymentFiles(string repositoryRoot)
    {
        return Directory.EnumerateFiles(repositoryRoot, "*", SearchOption.AllDirectories)
            .Where(file => !IsExcluded(repositoryRoot, file) && (IsDockerfile(file) || IsComposeFile(file)))
            .OrderBy(file => file, StringComparer.OrdinalIgnoreCase);
    }

    private static bool IsDockerfile(string file)
    {
        var name = Path.GetFileName(file);
        return string.Equals(name, "Dockerfile", StringComparison.OrdinalIgnoreCase) ||
            name.EndsWith(".Dockerfile", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(Path.GetExtension(file), ".dockerfile", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsComposeFile(string file)
    {
        var name = Path.GetFileName(file);
        return string.Equals(name, "docker-compose.yml", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(name, "docker-compose.yaml", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(name, "compose.yml", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(name, "compose.yaml", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsExcluded(string repositoryRoot, string file)
    {
        return RepositoryPathPolicy.IsIgnoredPath(repositoryRoot, file);
    }

    private static void AddJoined(Dictionary<string, string> metadata, string key, IEnumerable<string> values)
    {
        var joined = string.Join(",", values.Where(value => !string.IsNullOrWhiteSpace(value)).Distinct(StringComparer.OrdinalIgnoreCase));
        if (!string.IsNullOrWhiteSpace(joined))
        {
            metadata[key] = joined;
        }
    }

    private static string[] NormalizeLines(string text)
    {
        return text.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
    }

    private static int CountLines(string text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return 1;
        }

        return text.Count(character => character == '\n') + 1;
    }

    private static int LeadingSpaces(string line)
    {
        return line.TakeWhile(character => character == ' ').Count();
    }

    private static string FirstToken(string text)
    {
        var parts = text.Split([' ', '\t'], 2, StringSplitOptions.RemoveEmptyEntries);
        return parts.Length == 0 ? string.Empty : parts[0];
    }

    private static string Unquote(string value)
    {
        var trimmed = value.Trim();
        return trimmed.Length >= 2 &&
            ((trimmed[0] == '"' && trimmed[^1] == '"') || (trimmed[0] == '\'' && trimmed[^1] == '\''))
            ? trimmed[1..^1]
            : trimmed;
    }

    private static string ProjectName(string repositoryRoot)
    {
        return new DirectoryInfo(repositoryRoot).Name;
    }

    private static string NormalizePath(string path)
    {
        return path.Replace('\\', '/');
    }

    [GeneratedRegex(@"^\s*FROM\s+(?<image>\S+)(?:\s+AS\s+(?<alias>[A-Za-z0-9_.-]+))?", RegexOptions.IgnoreCase)]
    private static partial Regex FromRegex();

    [GeneratedRegex(@"^\s*(?<keyword>[A-Za-z]+)\s+(?<value>.+)$")]
    private static partial Regex DockerInstructionRegex();

    [GeneratedRegex(@"^services:\s*(?:#.*)?$")]
    private static partial Regex ServicesRegex();

    [GeneratedRegex(@"^(?<indent>\s*)(?<key>['""]?[^:'""]+['""]?)\s*:\s*(?<value>.*)$")]
    private static partial Regex MappingKeyRegex();

    private sealed record DockerfileStage(int LineNumber, string BaseImage, string? Alias);

    private sealed record ComposeService(string Name, int LineNumber, int EndLine);
}
