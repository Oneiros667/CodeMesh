namespace CodeMesh.Control.Configuration;

public static class EnvironmentFileLoader
{
    public static int LoadIfExists(string root, string fileName = ".env")
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(root);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileName);

        var path = Path.Combine(root, fileName);
        if (!File.Exists(path))
        {
            return 0;
        }

        var loaded = 0;
        foreach (var rawLine in File.ReadLines(path))
        {
            var line = rawLine.Trim();
            if (line.Length == 0 || line.StartsWith('#'))
            {
                continue;
            }

            var separator = line.IndexOf('=');
            if (separator <= 0)
            {
                continue;
            }

            var key = line[..separator].Trim();
            if (key.Length == 0 || Environment.GetEnvironmentVariable(key) is not null)
            {
                continue;
            }

            var value = Unquote(line[(separator + 1)..].Trim());
            Environment.SetEnvironmentVariable(key, value);
            loaded++;
        }

        return loaded;
    }

    private static string Unquote(string value)
    {
        if (value.Length >= 2 &&
            ((value[0] == '"' && value[^1] == '"') ||
             (value[0] == '\'' && value[^1] == '\'')))
        {
            return value[1..^1];
        }

        return value;
    }
}
