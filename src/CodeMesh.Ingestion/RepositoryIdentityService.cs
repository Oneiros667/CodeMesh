using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Serialization;
using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Utilities;
using CodeMesh.Storage;

namespace CodeMesh.Ingestion;

internal sealed record RepositoryIdentity(
    string ProjectId,
    string CheckoutId,
    string ProjectAlias,
    string MarkerPath,
    DateTimeOffset CreatedAt);

internal static class RepositoryIdentityService
{
    private const int FormatVersion = 1;
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public static async Task<RepositoryIdentity> ResolveAsync(
        string repositoryRoot,
        string? requestedProjectId,
        ISnapshotRegistryStore registry,
        CancellationToken cancellationToken)
    {
        var markerPaths = await ResolveMarkerPathsAsync(repositoryRoot, cancellationToken).ConfigureAwait(false);
        var projectMarker = await ReadProjectMarkerAsync(markerPaths.ProjectPath, cancellationToken).ConfigureAwait(false);
        var checkoutMarker = await ReadCheckoutMarkerAsync(markerPaths.CheckoutPath, cancellationToken).ConfigureAwait(false);
        var createdAt = checkoutMarker?.CreatedAtUtc ?? DateTimeOffset.UtcNow;
        var normalizedRequestedProjectId = NormalizeId(requestedProjectId, "prj");
        var projectId = normalizedRequestedProjectId
            ?? NormalizeId(projectMarker?.ProjectId, "prj")
            ?? NewId("prj");
        var checkoutId = NormalizeId(checkoutMarker?.CheckoutId, "chk") ?? NewId("chk");
        var existingProject = await registry
            .GetRepositoryAsync(projectId, cancellationToken)
            .ConfigureAwait(false);
        var projectAlias = projectMarker?.Alias
            ?? existingProject?.Alias
            ?? RepositoryAlias.FromPath(markerPaths.AliasSourcePath);

        var registered = await registry.GetCheckoutAsync(checkoutId, cancellationToken).ConfigureAwait(false);
        if (registered is not null &&
            !PathsEqual(registered.RootPath, repositoryRoot) &&
            Directory.Exists(registered.RootPath))
        {
            checkoutId = NewId("chk");
            createdAt = DateTimeOffset.UtcNow;
        }

        if (projectMarker is null ||
            !string.Equals(projectMarker.ProjectId, projectId, StringComparison.Ordinal) ||
            !string.Equals(projectMarker.Alias, projectAlias, StringComparison.Ordinal))
        {
            await WriteMarkerAsync(
                    markerPaths.ProjectPath,
                    new ProjectMarker(
                        FormatVersion,
                        projectId,
                        projectMarker?.CreatedAtUtc ?? DateTimeOffset.UtcNow,
                        projectAlias),
                    cancellationToken)
                .ConfigureAwait(false);
        }
        if (checkoutMarker is null || !string.Equals(checkoutMarker.CheckoutId, checkoutId, StringComparison.Ordinal))
        {
            await WriteMarkerAsync(
                    markerPaths.CheckoutPath,
                    new CheckoutMarker(FormatVersion, checkoutId, createdAt),
                    cancellationToken)
                .ConfigureAwait(false);
        }

        return new RepositoryIdentity(projectId, checkoutId, projectAlias, markerPaths.CheckoutPath, createdAt);
    }

    private static async Task<MarkerPaths> ResolveMarkerPathsAsync(
        string repositoryRoot,
        CancellationToken cancellationToken)
    {
        var gitDirectory = await RunGitAsync(repositoryRoot, ["rev-parse", "--path-format=absolute", "--git-dir"], cancellationToken)
            .ConfigureAwait(false);
        if (!string.IsNullOrWhiteSpace(gitDirectory))
        {
            var commonDirectory = await RunGitAsync(repositoryRoot, ["rev-parse", "--path-format=absolute", "--git-common-dir"], cancellationToken)
                .ConfigureAwait(false) ?? gitDirectory;
            return new MarkerPaths(
                Path.Combine(commonDirectory, "codemesh", "project.json"),
                Path.Combine(gitDirectory, "codemesh", "checkout.json"),
                Directory.GetParent(commonDirectory)?.FullName ?? repositoryRoot);
        }

        return new MarkerPaths(
            Path.Combine(repositoryRoot, ".codemesh", "project.json"),
            Path.Combine(repositoryRoot, ".codemesh", "checkout.json"),
            repositoryRoot);
    }

    private static Task<ProjectMarker?> ReadProjectMarkerAsync(string path, CancellationToken cancellationToken)
    {
        return ReadMarkerAsync<ProjectMarker>(path, cancellationToken);
    }

    private static Task<CheckoutMarker?> ReadCheckoutMarkerAsync(string path, CancellationToken cancellationToken)
    {
        return ReadMarkerAsync<CheckoutMarker>(path, cancellationToken);
    }

    private static async Task<TMarker?> ReadMarkerAsync<TMarker>(string path, CancellationToken cancellationToken)
        where TMarker : class, IIdentityMarker
    {
        if (!File.Exists(path))
        {
            return null;
        }

        try
        {
            await using var stream = File.OpenRead(path);
            var marker = await JsonSerializer.DeserializeAsync<TMarker>(stream, cancellationToken: cancellationToken)
                .ConfigureAwait(false);
            return marker is { FormatVersion: FormatVersion } ? marker : null;
        }
        catch (Exception exception) when (exception is IOException or JsonException or UnauthorizedAccessException)
        {
            throw new InvalidOperationException($"CodeMesh identity marker is unreadable: {path}", exception);
        }
    }

    private static async Task WriteMarkerAsync(
        string path,
        object marker,
        CancellationToken cancellationToken)
    {
        var directory = Path.GetDirectoryName(path)
            ?? throw new InvalidOperationException($"Identity marker path has no directory: {path}");
        Directory.CreateDirectory(directory);
        var temporaryPath = Path.Combine(directory, $"identity.{Guid.NewGuid():N}.tmp");
        try
        {
            await using (var stream = new FileStream(
                temporaryPath,
                FileMode.CreateNew,
                FileAccess.Write,
                FileShare.None,
                4096,
                FileOptions.Asynchronous))
            {
                await JsonSerializer.SerializeAsync(stream, marker, JsonOptions, cancellationToken)
                    .ConfigureAwait(false);
                await stream.FlushAsync(cancellationToken).ConfigureAwait(false);
            }

            File.Move(temporaryPath, path, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }

    private static async Task<string?> RunGitAsync(
        string root,
        IReadOnlyList<string> arguments,
        CancellationToken cancellationToken)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "git",
            WorkingDirectory = root,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };
        foreach (var argument in arguments)
        {
            startInfo.ArgumentList.Add(argument);
        }

        using var process = new Process { StartInfo = startInfo };
        try
        {
            if (!process.Start())
            {
                return null;
            }

            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            timeout.CancelAfter(TimeSpan.FromSeconds(5));
            var output = process.StandardOutput.ReadToEndAsync(timeout.Token);
            var error = process.StandardError.ReadToEndAsync(timeout.Token);
            await process.WaitForExitAsync(timeout.Token).ConfigureAwait(false);
            await Task.WhenAll(output, error).ConfigureAwait(false);
            return process.ExitCode == 0 ? output.Result.Trim() : null;
        }
        catch (Exception exception) when (
            exception is InvalidOperationException or System.ComponentModel.Win32Exception or OperationCanceledException)
        {
            return null;
        }
    }

    private static string NewId(string prefix) => $"{prefix}_{Guid.NewGuid():N}";

    private static string? NormalizeId(string? value, string prefix)
    {
        var trimmed = value?.Trim();
        if (string.IsNullOrWhiteSpace(trimmed))
        {
            return null;
        }

        if (!trimmed.StartsWith($"{prefix}_", StringComparison.Ordinal) ||
            trimmed.Any(character => !(char.IsAsciiLetterOrDigit(character) || character is '_' or '-')))
        {
            throw new InvalidOperationException($"Invalid {prefix} identity '{trimmed}'.");
        }

        return trimmed;
    }

    private static bool PathsEqual(string left, string right)
    {
        return string.Equals(
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(left)),
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(right)),
            OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal);
    }

    private interface IIdentityMarker
    {
        int FormatVersion { get; }
    }

    private sealed record MarkerPaths(string ProjectPath, string CheckoutPath, string AliasSourcePath);

    private sealed record ProjectMarker(
        [property: JsonPropertyName("format_version")] int FormatVersion,
        [property: JsonPropertyName("project_id")] string ProjectId,
        [property: JsonPropertyName("created_at_utc")] DateTimeOffset CreatedAtUtc,
        [property: JsonPropertyName("alias")] string? Alias = null) : IIdentityMarker;

    private sealed record CheckoutMarker(
        [property: JsonPropertyName("format_version")] int FormatVersion,
        [property: JsonPropertyName("checkout_id")] string CheckoutId,
        [property: JsonPropertyName("created_at_utc")] DateTimeOffset CreatedAtUtc) : IIdentityMarker;
}
