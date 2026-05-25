using CodeMesh.Storage;

namespace CodeMesh.Ingestion.Embedding;

public sealed record EmbeddingVerificationRequest(
    string RepositoryId,
    string Provider,
    string Model);

public sealed record EmbeddingVerificationIssue(
    string Kind,
    string NodeId,
    string? ExpectedContentHash,
    string? ActualContentHash,
    string? EmbeddingId,
    string Message);

public sealed record EmbeddingVerificationResult(
    string RepositoryId,
    string Provider,
    string Model,
    int ExpectedCount,
    int MatchingEmbeddingCount,
    int CurrentEmbeddingCount,
    int TotalRepositoryEmbeddingCount,
    int OtherProviderEmbeddingCount,
    int MissingCount,
    int OutdatedCount,
    int StaleCount,
    int DuplicateCount,
    bool IsComplete,
    IReadOnlyList<EmbeddingVerificationIssue> Issues);

public sealed class EmbeddingVerifier(
    IIncrementalGraphStore graphStore,
    IIncrementalVectorStore vectorStore)
{
    public async Task<EmbeddingVerificationResult> VerifyAsync(
        EmbeddingVerificationRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(request.RepositoryId);
        ArgumentException.ThrowIfNullOrWhiteSpace(request.Provider);
        ArgumentException.ThrowIfNullOrWhiteSpace(request.Model);

        var nodes = await graphStore
            .GetNodeStatesAsync(request.RepositoryId, cancellationToken)
            .ConfigureAwait(false);
        var embeddings = await vectorStore
            .GetEmbeddingStatesAsync(request.RepositoryId, cancellationToken)
            .ConfigureAwait(false);

        var expectedContentByNode = nodes
            .GroupBy(node => node.NodeId, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.First().ContentHash, StringComparer.Ordinal);
        var expectedKeys = nodes
            .Select(node => LookupKey(node.NodeId, node.ContentHash))
            .ToHashSet(StringComparer.Ordinal);
        var matchingEmbeddings = embeddings
            .Where(embedding =>
                string.Equals(embedding.Provider, request.Provider, StringComparison.Ordinal) &&
                string.Equals(embedding.Model, request.Model, StringComparison.Ordinal))
            .ToArray();
        var currentEmbeddings = matchingEmbeddings
            .Where(embedding => expectedKeys.Contains(LookupKey(embedding.NodeId, embedding.ContentHash)))
            .ToArray();
        var currentKeys = currentEmbeddings
            .Select(embedding => LookupKey(embedding.NodeId, embedding.ContentHash))
            .ToHashSet(StringComparer.Ordinal);
        var issues = new List<EmbeddingVerificationIssue>();

        if (nodes.Count == 0)
        {
            issues.Add(new EmbeddingVerificationIssue(
                "empty_graph",
                string.Empty,
                null,
                null,
                null,
                "No graph nodes were found for this repository id."));
        }

        foreach (var node in nodes.Where(node => !currentKeys.Contains(LookupKey(node.NodeId, node.ContentHash))))
        {
            issues.Add(new EmbeddingVerificationIssue(
                "missing",
                node.NodeId,
                node.ContentHash,
                null,
                null,
                "No embedding exists for the current node content."));
        }

        foreach (var embedding in matchingEmbeddings)
        {
            if (!expectedContentByNode.TryGetValue(embedding.NodeId, out var expectedContentHash))
            {
                issues.Add(new EmbeddingVerificationIssue(
                    "stale",
                    embedding.NodeId,
                    null,
                    embedding.ContentHash,
                    embedding.EmbeddingId,
                    "Embedding exists for a node that is no longer in the graph."));
                continue;
            }

            if (!string.Equals(expectedContentHash, embedding.ContentHash, StringComparison.Ordinal))
            {
                issues.Add(new EmbeddingVerificationIssue(
                    "outdated",
                    embedding.NodeId,
                    expectedContentHash,
                    embedding.ContentHash,
                    embedding.EmbeddingId,
                    "Embedding content hash does not match the current graph node content hash."));
            }
        }

        foreach (var duplicateGroup in currentEmbeddings.GroupBy(
            embedding => LookupKey(embedding.NodeId, embedding.ContentHash),
            StringComparer.Ordinal).Where(group => group.Count() > 1))
        {
            var duplicate = duplicateGroup.First();
            issues.Add(new EmbeddingVerificationIssue(
                "duplicate",
                duplicate.NodeId,
                duplicate.ContentHash,
                duplicate.ContentHash,
                duplicate.EmbeddingId,
                $"Multiple embeddings exist for the same current node content ({duplicateGroup.Count()})."));
        }

        var missingCount = issues.Count(issue => string.Equals(issue.Kind, "missing", StringComparison.Ordinal));
        var outdatedCount = issues.Count(issue => string.Equals(issue.Kind, "outdated", StringComparison.Ordinal));
        var staleCount = issues.Count(issue => string.Equals(issue.Kind, "stale", StringComparison.Ordinal));
        var duplicateCount = issues.Count(issue => string.Equals(issue.Kind, "duplicate", StringComparison.Ordinal));

        return new EmbeddingVerificationResult(
            request.RepositoryId,
            request.Provider,
            request.Model,
            nodes.Count,
            matchingEmbeddings.Length,
            currentEmbeddings.Length,
            embeddings.Count,
            embeddings.Count - matchingEmbeddings.Length,
            missingCount,
            outdatedCount,
            staleCount,
            duplicateCount,
            issues.Count == 0,
            issues);
    }

    private static string LookupKey(string nodeId, string contentHash)
    {
        return $"{nodeId}\u001f{contentHash}";
    }
}
