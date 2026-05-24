using System.Security.Cryptography;
using System.Text;

namespace CodeMesh.Domain.Utilities;

public static class CodeMeshHash
{
    public static string Sha256Hex(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    public static string StableId(params string?[] parts)
    {
        var normalized = string.Join('\u001f', parts.Select(part => part?.Trim() ?? string.Empty));
        return Sha256Hex(normalized);
    }
}
