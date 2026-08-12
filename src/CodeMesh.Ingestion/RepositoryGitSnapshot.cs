using System.Diagnostics;

namespace CodeMesh.Ingestion;

internal sealed record RepositoryGitSnapshot(
    string? RemoteUrl,
    string? Branch,
    string? Commit,
    bool WorkingTreeDirty)
{
    private static readonly TimeSpan GitTimeout = TimeSpan.FromSeconds(5);

    public static async Task<RepositoryGitSnapshot> CaptureAsync(
        string repositoryRoot,
        CancellationToken cancellationToken)
    {
        var commit = await RunGitAsync(
                repositoryRoot,
                ["rev-parse", "--verify", "HEAD"],
                cancellationToken)
            .ConfigureAwait(false);
        if (commit is null)
        {
            return new RepositoryGitSnapshot(null, null, null, false);
        }

        var branch = await RunGitAsync(
                repositoryRoot,
                ["symbolic-ref", "--quiet", "--short", "HEAD"],
                cancellationToken)
            .ConfigureAwait(false);
        var remoteUrl = await RunGitAsync(
                repositoryRoot,
                ["config", "--get", "remote.origin.url"],
                cancellationToken)
            .ConfigureAwait(false);
        var status = await RunGitAsync(
                repositoryRoot,
                ["status", "--porcelain", "--untracked-files=normal"],
                cancellationToken,
                allowEmpty: true)
            .ConfigureAwait(false);

        return new RepositoryGitSnapshot(remoteUrl, branch, commit, !string.IsNullOrEmpty(status));
    }

    private static async Task<string?> RunGitAsync(
        string repositoryRoot,
        IReadOnlyList<string> arguments,
        CancellationToken cancellationToken,
        bool allowEmpty = false)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "git",
            WorkingDirectory = repositoryRoot,
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
            timeout.CancelAfter(GitTimeout);
            var standardOutput = process.StandardOutput.ReadToEndAsync(timeout.Token);
            var standardError = process.StandardError.ReadToEndAsync(timeout.Token);
            await process.WaitForExitAsync(timeout.Token).ConfigureAwait(false);
            await Task.WhenAll(standardOutput, standardError).ConfigureAwait(false);

            if (process.ExitCode != 0)
            {
                return null;
            }

            var value = standardOutput.Result.Trim();
            return string.IsNullOrWhiteSpace(value) && !allowEmpty ? null : value;
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            TryKill(process);
            return null;
        }
        catch (Exception exception) when (
            exception is InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            return null;
        }
    }

    private static void TryKill(Process process)
    {
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (InvalidOperationException)
        {
        }
    }
}
