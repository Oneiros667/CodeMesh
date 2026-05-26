using System.Text;

namespace CodeMesh.Domain.Utilities;

public static class RepositoryAlias
{
    public static string FromPath(string repositoryRoot)
    {
        var trimmed = repositoryRoot.TrimEnd(
            Path.DirectorySeparatorChar,
            Path.AltDirectorySeparatorChar);
        var name = Path.GetFileName(trimmed);

        return Normalize(string.IsNullOrWhiteSpace(name) ? trimmed : name);
    }

    public static string Normalize(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "repository";
        }

        var builder = new StringBuilder(value.Length);
        var previousWasSeparator = true;

        for (var i = 0; i < value.Length; i++)
        {
            var current = value[i];
            if (!char.IsLetterOrDigit(current))
            {
                AppendSeparator(builder, ref previousWasSeparator);
                continue;
            }

            if (ShouldSplitWord(value, i) && !previousWasSeparator)
            {
                AppendSeparator(builder, ref previousWasSeparator);
            }

            builder.Append(char.ToLowerInvariant(current));
            previousWasSeparator = false;
        }

        var alias = builder.ToString().Trim('_');
        return alias.Length == 0 ? "repository" : alias;
    }

    private static bool ShouldSplitWord(string value, int index)
    {
        var current = value[index];
        if (!char.IsUpper(current) || index == 0)
        {
            return false;
        }

        var previous = value[index - 1];
        var next = index + 1 < value.Length ? value[index + 1] : '\0';

        return char.IsLower(previous) ||
            char.IsDigit(previous) ||
            (char.IsUpper(previous) && next != '\0' && char.IsLower(next));
    }

    private static void AppendSeparator(StringBuilder builder, ref bool previousWasSeparator)
    {
        if (!previousWasSeparator && builder.Length > 0)
        {
            builder.Append('_');
        }

        previousWasSeparator = true;
    }
}
