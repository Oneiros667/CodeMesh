using System.Collections.Concurrent;
using System.Text;
using System.Text.RegularExpressions;
using CodeMesh.Domain.Contracts;

namespace CodeMesh.Domain.Utilities;

public static class RepositoryPathPolicy
{
    public const string Version = "repository-path-policy-v2";

    private static readonly RepositoryPathFilter DefaultFilter = new();
    private static readonly ConcurrentDictionary<string, Regex> GlobExpressions = new(StringComparer.Ordinal);

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

    private static readonly HashSet<string> KnownSecretFileNames = new(StringComparer.OrdinalIgnoreCase)
    {
        ".env",
        ".envrc",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "application_default_credentials.json",
        "accesstokens.json",
        "credentials",
        "credentials.json",
        "credentials.toml",
        "credentials.xml",
        "credentials.yaml",
        "credentials.yml",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "kubeconfig",
        "secrets.json",
        "secrets.toml",
        "secrets.xml",
        "secrets.yaml",
        "secrets.yml"
    };

    private static readonly HashSet<string> KnownSecretExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".jks",
        ".kdbx",
        ".key",
        ".keystore",
        ".p12",
        ".pem",
        ".pfx",
        ".snk",
        ".tfstate"
    };

    private static readonly HashSet<string> SafeEnvironmentTemplateNames = new(StringComparer.OrdinalIgnoreCase)
    {
        ".env.defaults",
        ".env.example",
        ".env.sample",
        ".env.template"
    };

    public static bool IsIgnoredPath(
        string repositoryRoot,
        string candidatePath,
        RepositoryPathFilter? filter = null)
    {
        var root = Path.GetFullPath(repositoryRoot);
        var candidate = Path.GetFullPath(candidatePath);
        var relativePath = Path.GetRelativePath(root, candidate);
        return IsIgnoredRelativePath(relativePath, filter) ||
            ContainsReparsePoint(root, relativePath);
    }

    public static bool IsIgnoredRelativePath(
        string relativePath,
        RepositoryPathFilter? filter = null)
    {
        var normalizedPath = NormalizeRelativePath(relativePath);
        if (normalizedPath.Length == 0 ||
            Path.IsPathRooted(normalizedPath) ||
            IsOutsideRepository(normalizedPath))
        {
            return true;
        }

        var segments = normalizedPath.Split('/', StringSplitOptions.RemoveEmptyEntries);
        if (segments.Any(IsIgnoredSegment))
        {
            return true;
        }

        var effectiveFilter = filter ?? DefaultFilter;
        if (effectiveFilter.ExcludeKnownSecretFiles && IsKnownSecretFile(normalizedPath))
        {
            return true;
        }

        var denyPatterns = NormalizePatterns(effectiveFilter.DenyPatterns, nameof(effectiveFilter.DenyPatterns));
        if (denyPatterns.Any(pattern => MatchesGlob(normalizedPath, pattern)))
        {
            return true;
        }

        var allowPatterns = NormalizePatterns(effectiveFilter.AllowPatterns, nameof(effectiveFilter.AllowPatterns));
        return allowPatterns.Count > 0 &&
            !allowPatterns.Any(pattern => MatchesGlob(normalizedPath, pattern));
    }

    public static IEnumerable<string> EnumerateFiles(
        string repositoryRoot,
        string searchPattern,
        RepositoryPathFilter? filter = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoryRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(searchPattern);

        var root = Path.GetFullPath(repositoryRoot);
        var pending = new Stack<string>();
        pending.Push(root);

        while (pending.Count > 0)
        {
            var directory = pending.Pop();
            foreach (var child in Directory.EnumerateDirectories(directory))
            {
                // Apply immutable generated/cache and link containment here,
                // but defer allow/deny filters until a concrete file path is known.
                if (!IsIgnoredPath(root, child))
                {
                    pending.Push(child);
                }
            }

            foreach (var file in Directory.EnumerateFiles(directory, searchPattern, SearchOption.TopDirectoryOnly))
            {
                if (!IsIgnoredPath(root, file, filter))
                {
                    yield return file;
                }
            }
        }
    }

    public static string StableFingerprint(RepositoryPathFilter? filter)
    {
        var effectiveFilter = filter ?? DefaultFilter;
        var allowPatterns = NormalizePatterns(effectiveFilter.AllowPatterns, nameof(effectiveFilter.AllowPatterns));
        var denyPatterns = NormalizePatterns(effectiveFilter.DenyPatterns, nameof(effectiveFilter.DenyPatterns));
        return string.Join(
            '\u001e',
            Version,
            effectiveFilter.ExcludeKnownSecretFiles ? "exclude-known-secrets" : "include-known-secrets",
            $"allow={string.Join('\u001d', allowPatterns.OrderBy(value => value, StringComparer.OrdinalIgnoreCase))}",
            $"deny={string.Join('\u001d', denyPatterns.OrderBy(value => value, StringComparer.OrdinalIgnoreCase))}");
    }

    private static bool IsIgnoredSegment(string segment)
    {
        return IgnoredDirectoryNames.Contains(segment) ||
            segment.EndsWith(".egg-info", StringComparison.OrdinalIgnoreCase);
    }

    private static bool ContainsReparsePoint(string repositoryRoot, string relativePath)
    {
        var current = repositoryRoot;
        foreach (var segment in relativePath.Split(
                     ['/', '\\'],
                     StringSplitOptions.RemoveEmptyEntries))
        {
            current = Path.Combine(current, segment);
            try
            {
                if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                {
                    return true;
                }
            }
            catch (Exception exception) when (
                exception is FileNotFoundException or
                DirectoryNotFoundException or
                UnauthorizedAccessException or
                IOException)
            {
                return true;
            }
        }

        return false;
    }

    private static bool IsKnownSecretFile(string normalizedPath)
    {
        var fileName = normalizedPath[(normalizedPath.LastIndexOf('/') + 1)..];
        if (IsSafeEnvironmentTemplate(fileName))
        {
            return false;
        }

        if (fileName.StartsWith(".env.", StringComparison.OrdinalIgnoreCase) ||
            IsServiceAccountFile(fileName) ||
            KnownSecretFileNames.Contains(fileName) ||
            KnownSecretExtensions.Contains(Path.GetExtension(fileName)) ||
            fileName.EndsWith(".tfstate.backup", StringComparison.OrdinalIgnoreCase) ||
            IsPrivateKeyName(fileName))
        {
            return true;
        }

        return normalizedPath.Equals(".aws/credentials", StringComparison.OrdinalIgnoreCase) ||
            normalizedPath.Equals(".docker/config.json", StringComparison.OrdinalIgnoreCase) ||
            normalizedPath.Equals(
                ".config/gcloud/application_default_credentials.json",
                StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsPrivateKeyName(string fileName)
    {
        return fileName.StartsWith("id_rsa_", StringComparison.OrdinalIgnoreCase) ||
            fileName.StartsWith("id_dsa_", StringComparison.OrdinalIgnoreCase) ||
            fileName.StartsWith("id_ecdsa_", StringComparison.OrdinalIgnoreCase) ||
            fileName.StartsWith("id_ed25519_", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsServiceAccountFile(string fileName)
    {
        return (fileName.StartsWith("service-account", StringComparison.OrdinalIgnoreCase) ||
                fileName.StartsWith("service_account", StringComparison.OrdinalIgnoreCase)) &&
            string.Equals(Path.GetExtension(fileName), ".json", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsSafeEnvironmentTemplate(string fileName)
    {
        return SafeEnvironmentTemplateNames.Contains(fileName) ||
            fileName.StartsWith(".env.", StringComparison.OrdinalIgnoreCase) &&
            (fileName.EndsWith(".defaults", StringComparison.OrdinalIgnoreCase) ||
             fileName.EndsWith(".example", StringComparison.OrdinalIgnoreCase) ||
             fileName.EndsWith(".sample", StringComparison.OrdinalIgnoreCase) ||
             fileName.EndsWith(".template", StringComparison.OrdinalIgnoreCase));
    }

    private static IReadOnlyList<string> NormalizePatterns(
        IReadOnlyList<string>? patterns,
        string parameterName)
    {
        if (patterns is null || patterns.Count == 0)
        {
            return Array.Empty<string>();
        }

        return patterns
            .Select(pattern => NormalizePattern(pattern, parameterName))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static string NormalizePattern(string pattern, string parameterName)
    {
        if (string.IsNullOrWhiteSpace(pattern))
        {
            throw new ArgumentException("Repository path patterns must not be empty.", parameterName);
        }

        var normalized = pattern.Trim().Replace('\\', '/');
        while (normalized.StartsWith("./", StringComparison.Ordinal))
        {
            normalized = normalized[2..];
        }

        var segments = normalized.Split('/');
        if (normalized.Any(char.IsControl) ||
            normalized.Contains("//", StringComparison.Ordinal) ||
            normalized.StartsWith("/", StringComparison.Ordinal) ||
            Regex.IsMatch(normalized, "^[a-z]:/", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant) ||
            Path.IsPathRooted(normalized) ||
            segments.Contains(".", StringComparer.Ordinal) ||
            segments.Contains("..", StringComparer.Ordinal))
        {
            throw new ArgumentException(
                $"Repository path pattern must be repository-relative and must not traverse parents: {pattern}",
                parameterName);
        }

        if (normalized.EndsWith("/", StringComparison.Ordinal))
        {
            normalized += "**";
        }

        return normalized.ToLowerInvariant();
    }

    private static bool MatchesGlob(string normalizedPath, string normalizedPattern)
    {
        var regex = GlobExpressions.GetOrAdd(normalizedPattern, CreateGlobExpression);
        return regex.IsMatch(normalizedPath);
    }

    private static Regex CreateGlobExpression(string normalizedPattern)
    {
        var expression = new StringBuilder("^");
        for (var index = 0; index < normalizedPattern.Length; index++)
        {
            var character = normalizedPattern[index];
            if (character == '*' && index + 1 < normalizedPattern.Length && normalizedPattern[index + 1] == '*')
            {
                if (index + 2 < normalizedPattern.Length && normalizedPattern[index + 2] == '/')
                {
                    expression.Append("(?:.*/)?");
                    index += 2;
                }
                else
                {
                    expression.Append(".*");
                    index++;
                }
                continue;
            }

            expression.Append(character switch
            {
                '*' => "[^/]*",
                '?' => "[^/]",
                _ => Regex.Escape(character.ToString())
            });
        }

        expression.Append('$');
        return new Regex(
            expression.ToString(),
            RegexOptions.CultureInvariant | RegexOptions.IgnoreCase,
            TimeSpan.FromSeconds(1));
    }

    private static string NormalizeRelativePath(string relativePath)
    {
        var normalized = relativePath.Trim().Replace('\\', '/');
        while (normalized.StartsWith("./", StringComparison.Ordinal))
        {
            normalized = normalized[2..];
        }
        return normalized;
    }

    private static bool IsOutsideRepository(string normalizedPath)
    {
        return normalizedPath.Equals("..", StringComparison.Ordinal) ||
            normalizedPath.StartsWith("../", StringComparison.Ordinal);
    }
}
