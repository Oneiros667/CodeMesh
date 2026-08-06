using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Health;
using MongoDB.Bson.Serialization.Attributes;
using MongoDB.Driver;

namespace CodeMesh.Storage.Mongo;

public sealed record MongoNodeSummaryStoreOptions(
    string ConnectionString,
    string DatabaseName,
    string CollectionName = "node_summaries",
    TimeSpan? ServerSelectionTimeout = null);

public sealed class MongoNodeSummaryStore :
    INodeSummaryStore,
    IIncrementalNodeSummaryStore,
    INodeSummaryCoverageStore,
    IStoreHealthCheck
{
    private readonly IMongoDatabase _database;
    private readonly IMongoCollection<NodeSummaryDocument> _summaries;
    private int _indexesEnsured;

    public MongoNodeSummaryStore(MongoNodeSummaryStoreOptions options)
        : this(CreateClient(options), options.DatabaseName, options.CollectionName)
    {
    }

    public MongoNodeSummaryStore(IMongoClient client, string databaseName, string collectionName = "node_summaries")
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(databaseName);
        ArgumentException.ThrowIfNullOrWhiteSpace(collectionName);

        _database = client.GetDatabase(databaseName);
        _summaries = _database.GetCollection<NodeSummaryDocument>(collectionName);
        Name = $"mongodb:{databaseName}.{collectionName}";
    }

    public string Name { get; }

    public async Task UpsertSummariesAsync(
        IReadOnlyList<CodeNodeSummary> summaries,
        CancellationToken cancellationToken = default)
    {
        if (summaries.Count == 0)
        {
            return;
        }

        await EnsureIndexesAsync(cancellationToken).ConfigureAwait(false);

        var models = summaries
            .Select(summary => new ReplaceOneModel<NodeSummaryDocument>(
                Builders<NodeSummaryDocument>.Filter.Eq(item => item.Id, summary.Id),
                NodeSummaryDocument.FromDomain(summary))
            {
                IsUpsert = true
            })
            .ToArray();

        await _summaries.BulkWriteAsync(models, cancellationToken: cancellationToken)
            .ConfigureAwait(false);
    }

    public async Task<IReadOnlyList<StoredNodeSummaryState>> GetSummaryStatesAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        await EnsureIndexesAsync(cancellationToken).ConfigureAwait(false);

        var filter = Builders<NodeSummaryDocument>.Filter.Eq(item => item.RepositoryId, repositoryId);
        var documents = await _summaries
            .Find(filter)
            .Project(item => new SummaryStateProjection
            {
                Id = item.Id,
                NodeId = item.NodeId,
                ContentHash = item.ContentHash,
                SummaryKind = item.SummaryKind,
                Provider = item.Provider,
                Model = item.Model,
                PromptVersion = item.PromptVersion,
                GenerationConfigurationFingerprint = item.GenerationConfigurationFingerprint,
                Status = item.Status
            })
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        return documents
            .Select(item => new StoredNodeSummaryState(
                item.Id,
                item.NodeId,
                item.ContentHash,
                item.SummaryKind,
                item.Provider,
                item.Model,
                item.PromptVersion,
                item.GenerationConfigurationFingerprint,
                item.Status))
            .ToArray();
    }

    public async Task RemoveSummariesExceptAsync(
        string repositoryId,
        IReadOnlySet<string> currentSummaryIds,
        CancellationToken cancellationToken = default)
    {
        await EnsureIndexesAsync(cancellationToken).ConfigureAwait(false);

        var filter = Builders<NodeSummaryDocument>.Filter.Eq(item => item.RepositoryId, repositoryId);
        if (currentSummaryIds.Count > 0)
        {
            filter &= Builders<NodeSummaryDocument>.Filter.Nin(item => item.Id, currentSummaryIds.ToArray());
        }

        await _summaries.DeleteManyAsync(filter, cancellationToken)
            .ConfigureAwait(false);
    }

    public async Task<NodeSummaryCoverage> GetSummaryCoverageAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        await EnsureIndexesAsync(cancellationToken).ConfigureAwait(false);

        var filter = Builders<NodeSummaryDocument>.Filter.Eq(item => item.RepositoryId, repositoryId);
        var summaries = await _summaries
            .Find(filter)
            .Project(item => new SummaryCoverageProjection
            {
                Id = item.Id,
                NodeId = item.NodeId,
                Kind = item.Kind,
                Name = item.Name,
                Provider = item.Provider,
                Model = item.Model,
                PromptVersion = item.PromptVersion,
                Status = item.Status,
                Error = item.Error,
                GeneratedAtUtc = item.GeneratedAtUtc
            })
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        return new NodeSummaryCoverage(
            repositoryId,
            summaries.Count,
            summaries.Count(summary => string.Equals(summary.Status, "completed", StringComparison.Ordinal)),
            summaries.Count(summary => string.Equals(summary.Status, "failed", StringComparison.Ordinal)),
            CountBy(summaries, summary => summary.Status),
            CountBy(summaries, summary => summary.Kind),
            CountBy(summaries, summary => $"{summary.Provider}/{summary.Model}/{summary.PromptVersion}"),
            CountProviderModels(summaries),
            summaries
                .Where(summary => string.Equals(summary.Status, "failed", StringComparison.Ordinal))
                .OrderByDescending(summary => summary.GeneratedAtUtc)
                .Take(10)
                .Select(summary => new NodeSummaryFailure(
                    summary.Id,
                    summary.NodeId,
                    summary.Kind,
                    summary.Name,
                    summary.Provider,
                    summary.Model,
                    summary.PromptVersion,
                    summary.Error ?? string.Empty,
                    new DateTimeOffset(DateTime.SpecifyKind(summary.GeneratedAtUtc, DateTimeKind.Utc))))
                .ToArray());
    }

    public async Task<ComponentHealth> CheckAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            var command = new MongoDB.Bson.BsonDocument("ping", 1);
            await _database.RunCommandAsync<MongoDB.Bson.BsonDocument>(command, cancellationToken: cancellationToken)
                .ConfigureAwait(false);

            return new ComponentHealth(
                Name,
                ComponentState.Healthy,
                "MongoDB node summary store is available.",
                new Dictionary<string, string>
                {
                    ["database"] = _database.DatabaseNamespace.DatabaseName,
                    ["collection"] = _summaries.CollectionNamespace.CollectionName
                });
        }
        catch (Exception exception) when (exception is MongoException or TimeoutException)
        {
            return new ComponentHealth(
                Name,
                ComponentState.Degraded,
                "MongoDB node summary store is not reachable.",
                new Dictionary<string, string>
                {
                    ["database"] = _database.DatabaseNamespace.DatabaseName,
                    ["collection"] = _summaries.CollectionNamespace.CollectionName,
                    ["detail"] = exception.Message
                });
        }
    }

    private static IMongoClient CreateClient(MongoNodeSummaryStoreOptions options)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(options.ConnectionString);
        ArgumentException.ThrowIfNullOrWhiteSpace(options.DatabaseName);

        var settings = MongoClientSettings.FromConnectionString(options.ConnectionString);
        settings.ServerSelectionTimeout = options.ServerSelectionTimeout ?? TimeSpan.FromSeconds(2);

        return new MongoClient(settings);
    }

    private async Task EnsureIndexesAsync(CancellationToken cancellationToken)
    {
        if (Interlocked.Exchange(ref _indexesEnsured, 1) == 1)
        {
            return;
        }

        var indexes = new[]
        {
            new CreateIndexModel<NodeSummaryDocument>(
                Builders<NodeSummaryDocument>.IndexKeys
                    .Ascending(item => item.RepositoryId)
                    .Ascending(item => item.NodeId)
                    .Ascending(item => item.ContentHash)
                    .Ascending(item => item.SummaryKind)
                    .Ascending(item => item.Provider)
                    .Ascending(item => item.Model)
                    .Ascending(item => item.PromptVersion)
                    .Ascending(item => item.GenerationConfigurationFingerprint),
                new CreateIndexOptions
                {
                    Name = "node_summary_identity_v2",
                    Unique = true
                }),
            new CreateIndexModel<NodeSummaryDocument>(
                Builders<NodeSummaryDocument>.IndexKeys
                    .Ascending(item => item.RepositoryId)
                    .Ascending(item => item.NodeId),
                new CreateIndexOptions { Name = "repository_node" }),
            new CreateIndexModel<NodeSummaryDocument>(
                Builders<NodeSummaryDocument>.IndexKeys
                    .Ascending(item => item.RepositoryId)
                    .Ascending(item => item.Kind)
                    .Ascending(item => item.Name),
                new CreateIndexOptions { Name = "repository_kind_name" }),
            new CreateIndexModel<NodeSummaryDocument>(
                Builders<NodeSummaryDocument>.IndexKeys
                    .Ascending(item => item.RepositoryId)
                    .Ascending(item => item.ContentHash),
                new CreateIndexOptions { Name = "repository_content_hash" })
        };

        await DropLegacyIdentityIndexAsync(cancellationToken).ConfigureAwait(false);
        await _summaries.Indexes.CreateManyAsync(indexes, cancellationToken)
            .ConfigureAwait(false);
    }

    private async Task DropLegacyIdentityIndexAsync(CancellationToken cancellationToken)
    {
        try
        {
            await _summaries.Indexes
                .DropOneAsync("node_summary_identity", cancellationToken)
                .ConfigureAwait(false);
        }
        catch (MongoCommandException exception) when (
            string.Equals(exception.CodeName, "IndexNotFound", StringComparison.Ordinal))
        {
            // The collection is already new or has already completed this index migration.
        }
    }

    private static IReadOnlyDictionary<string, int> CountBy<T>(
        IEnumerable<T> items,
        Func<T, string> keySelector)
    {
        return items
            .GroupBy(item =>
            {
                var key = keySelector(item);
                return string.IsNullOrWhiteSpace(key) ? "unknown" : key;
            }, StringComparer.Ordinal)
            .OrderByDescending(group => group.Count())
            .ThenBy(group => group.Key, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Count(), StringComparer.Ordinal);
    }

    private static IReadOnlyList<NodeSummaryProviderModelCount> CountProviderModels(
        IEnumerable<SummaryCoverageProjection> summaries)
    {
        return summaries
            .GroupBy(summary => new
            {
                Provider = string.IsNullOrWhiteSpace(summary.Provider) ? "unknown" : summary.Provider,
                Model = string.IsNullOrWhiteSpace(summary.Model) ? "unknown" : summary.Model,
                PromptVersion = string.IsNullOrWhiteSpace(summary.PromptVersion) ? "unknown" : summary.PromptVersion
            })
            .OrderByDescending(group => group.Count())
            .ThenBy(group => group.Key.Provider, StringComparer.Ordinal)
            .ThenBy(group => group.Key.Model, StringComparer.Ordinal)
            .ThenBy(group => group.Key.PromptVersion, StringComparer.Ordinal)
            .Select(group => new NodeSummaryProviderModelCount(
                group.Key.Provider,
                group.Key.Model,
                group.Key.PromptVersion,
                group.Count()))
            .ToArray();
    }

    private sealed class NodeSummaryDocument
    {
        [BsonId]
        [BsonElement("_id")]
        public required string Id { get; init; }

        [BsonElement("repositoryId")]
        public required string RepositoryId { get; init; }

        [BsonElement("repositoryRoot")]
        public required string RepositoryRoot { get; init; }

        [BsonElement("ingestionRunId")]
        public required string IngestionRunId { get; init; }

        [BsonElement("nodeId")]
        public required string NodeId { get; init; }

        [BsonElement("stableKey")]
        public required string StableKey { get; init; }

        [BsonElement("kind")]
        public required string Kind { get; init; }

        [BsonElement("name")]
        public required string Name { get; init; }

        [BsonElement("language")]
        public required string Language { get; init; }

        [BsonElement("project")]
        public required string Project { get; init; }

        [BsonElement("filePath")]
        public required string FilePath { get; init; }

        [BsonElement("startLine")]
        public required int StartLine { get; init; }

        [BsonElement("startColumn")]
        public required int StartColumn { get; init; }

        [BsonElement("endLine")]
        public required int EndLine { get; init; }

        [BsonElement("endColumn")]
        public required int EndColumn { get; init; }

        [BsonElement("contentHash")]
        public required string ContentHash { get; init; }

        [BsonElement("summaryKind")]
        public required string SummaryKind { get; init; }

        [BsonElement("summary")]
        public required string Summary { get; init; }

        [BsonElement("tags")]
        public IReadOnlyList<string> Tags { get; init; } = [];

        [BsonElement("confidence")]
        public required string Confidence { get; init; }

        [BsonElement("provider")]
        public required string Provider { get; init; }

        [BsonElement("model")]
        public required string Model { get; init; }

        [BsonElement("promptVersion")]
        public required string PromptVersion { get; init; }

        [BsonElement("generationConfigurationFingerprint")]
        public string GenerationConfigurationFingerprint { get; init; } = "legacy";

        [BsonElement("promptHash")]
        public required string PromptHash { get; init; }

        [BsonElement("generatedAtUtc")]
        public required DateTime GeneratedAtUtc { get; init; }

        [BsonElement("status")]
        public required string Status { get; init; }

        [BsonElement("error")]
        public string? Error { get; init; }

        [BsonElement("metadata")]
        public IReadOnlyDictionary<string, string> Metadata { get; init; } = new Dictionary<string, string>(StringComparer.Ordinal);

        public static NodeSummaryDocument FromDomain(CodeNodeSummary summary)
        {
            return new NodeSummaryDocument
            {
                Id = summary.Id,
                RepositoryId = summary.RepositoryId,
                RepositoryRoot = summary.RepositoryRoot,
                IngestionRunId = summary.IngestionRunId,
                NodeId = summary.NodeId,
                StableKey = summary.StableKey,
                Kind = summary.Kind.ToString(),
                Name = summary.Name,
                Language = summary.Language,
                Project = summary.Project,
                FilePath = summary.Span.FilePath,
                StartLine = summary.Span.StartLine,
                StartColumn = summary.Span.StartColumn,
                EndLine = summary.Span.EndLine,
                EndColumn = summary.Span.EndColumn,
                ContentHash = summary.ContentHash,
                SummaryKind = summary.SummaryKind,
                Summary = summary.Summary,
                Tags = summary.Tags,
                Confidence = summary.Confidence,
                Provider = summary.Provider,
                Model = summary.Model,
                PromptVersion = summary.PromptVersion,
                GenerationConfigurationFingerprint = summary.GenerationConfigurationFingerprint,
                PromptHash = summary.PromptHash,
                GeneratedAtUtc = summary.GeneratedAt.UtcDateTime,
                Status = summary.Status,
                Error = summary.Error,
                Metadata = summary.Metadata
            };
        }
    }

    private sealed class SummaryStateProjection
    {
        public required string Id { get; init; }

        public required string NodeId { get; init; }

        public required string ContentHash { get; init; }

        public required string SummaryKind { get; init; }

        public required string Provider { get; init; }

        public required string Model { get; init; }

        public required string PromptVersion { get; init; }

        public string GenerationConfigurationFingerprint { get; init; } = "legacy";

        public required string Status { get; init; }
    }

    private sealed class SummaryCoverageProjection
    {
        public required string Id { get; init; }

        public required string NodeId { get; init; }

        public required string Kind { get; init; }

        public required string Name { get; init; }

        public required string Provider { get; init; }

        public required string Model { get; init; }

        public required string PromptVersion { get; init; }

        public required string Status { get; init; }

        public string? Error { get; init; }

        public required DateTime GeneratedAtUtc { get; init; }
    }
}
