using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Health;
using CodeMesh.Domain.Utilities;
using MongoDB.Bson.Serialization.Attributes;
using MongoDB.Driver;

namespace CodeMesh.Storage.Mongo;

public sealed record MongoRegistryStoreOptions(
    string ConnectionString,
    string DatabaseName,
    string RepositoriesCollectionName = "repositories",
    string RunsCollectionName = "ingestion_runs",
    TimeSpan? ServerSelectionTimeout = null);

public sealed class MongoRegistryStore : IRegistryStore, IStoreHealthCheck
{
    private readonly IMongoDatabase _database;
    private readonly IMongoCollection<RepositoryDocument> _repositories;
    private readonly IMongoCollection<IngestionRunDocument> _runs;

    public MongoRegistryStore(MongoRegistryStoreOptions options)
        : this(CreateClient(options), options.DatabaseName, options.RepositoriesCollectionName, options.RunsCollectionName)
    {
    }

    public MongoRegistryStore(
        IMongoClient client,
        string databaseName,
        string repositoriesCollectionName = "repositories",
        string runsCollectionName = "ingestion_runs")
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(databaseName);
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoriesCollectionName);
        ArgumentException.ThrowIfNullOrWhiteSpace(runsCollectionName);

        _database = client.GetDatabase(databaseName);
        _repositories = _database.GetCollection<RepositoryDocument>(repositoriesCollectionName);
        _runs = _database.GetCollection<IngestionRunDocument>(runsCollectionName);
        Name = $"mongodb:{databaseName}.{repositoriesCollectionName}/{runsCollectionName}";
    }

    public string Name { get; }

    public async Task UpsertRepositoryAsync(
        RepositoryIndexRecord repository,
        CancellationToken cancellationToken = default)
    {
        var filter = Builders<RepositoryDocument>.Filter.Eq(item => item.RepositoryId, repository.RepositoryId);
        var alias = repository.Alias ?? MetadataAlias(repository.Metadata);
        var update = Builders<RepositoryDocument>.Update
            .SetOnInsert(item => item.RepositoryId, repository.RepositoryId)
            .SetOnInsert(item => item.FirstSeenAtUtc, repository.FirstSeenAt.UtcDateTime)
            .Set(item => item.RootPath, repository.RootPath)
            .Set(item => item.Alias, alias)
            .Set(item => item.RemoteUrl, repository.RemoteUrl)
            .Set(item => item.Branch, repository.Branch)
            .Set(item => item.Commit, repository.Commit)
            .Set(item => item.LastSeenAtUtc, repository.LastSeenAt.UtcDateTime)
            .Set(item => item.LastRunId, repository.LastRunId)
            .Set(item => item.LastStage, repository.LastStage?.ToString())
            .Set(item => item.LastMessage, repository.LastMessage)
            .Set(item => item.NodeCount, repository.NodeCount)
            .Set(item => item.RelationshipCount, repository.RelationshipCount)
            .Set(item => item.ContentCount, repository.ContentCount)
            .Set(item => item.Metadata, new Dictionary<string, string>(repository.Metadata, StringComparer.Ordinal));

        if (repository.EmbeddingCount.HasValue)
        {
            update = update.Set(item => item.EmbeddingCount, repository.EmbeddingCount.Value);
        }

        await _repositories.UpdateOneAsync(
                filter,
                update,
                new UpdateOptions { IsUpsert = true },
                cancellationToken)
            .ConfigureAwait(false);
    }

    public async Task UpsertRunAsync(
        IngestionRunIndexRecord run,
        CancellationToken cancellationToken = default)
    {
        var filter = Builders<IngestionRunDocument>.Filter.Eq(item => item.RunId, run.RunId);
        var document = IngestionRunDocument.FromDomain(run);

        await _runs.ReplaceOneAsync(
                filter,
                document,
                new ReplaceOptions { IsUpsert = true },
                cancellationToken)
            .ConfigureAwait(false);
    }

    public async Task<IReadOnlyList<RepositoryIndexRecord>> ListRepositoriesAsync(
        int limit = 50,
        CancellationToken cancellationToken = default)
    {
        var documents = await _repositories
            .Find(Builders<RepositoryDocument>.Filter.Empty)
            .SortByDescending(item => item.LastSeenAtUtc)
            .Limit(Math.Clamp(limit, 1, 500))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        return documents.Select(document => document.ToDomain()).ToArray();
    }

    public async Task<RepositoryIndexRecord?> GetRepositoryAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        var normalizedAlias = RepositoryAlias.Normalize(repositoryId);
        var filter = Builders<RepositoryDocument>.Filter.Or(
            Builders<RepositoryDocument>.Filter.Eq(item => item.RepositoryId, repositoryId),
            Builders<RepositoryDocument>.Filter.Eq(item => item.Alias, repositoryId),
            Builders<RepositoryDocument>.Filter.Eq(item => item.Alias, normalizedAlias),
            Builders<RepositoryDocument>.Filter.Eq("metadata.alias", repositoryId),
            Builders<RepositoryDocument>.Filter.Eq("metadata.alias", normalizedAlias));
        var documents = await _repositories
            .Find(filter)
            .Limit(3)
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        var exact = documents.FirstOrDefault(document =>
            string.Equals(document.RepositoryId, repositoryId, StringComparison.Ordinal));
        if (exact is not null)
        {
            return exact.ToDomain();
        }

        var distinct = documents
            .GroupBy(document => document.RepositoryId, StringComparer.Ordinal)
            .Select(group => group.First())
            .ToArray();
        if (distinct.Length > 1)
        {
            throw new InvalidOperationException($"Repository alias '{repositoryId}' matches multiple repositories.");
        }

        return distinct.FirstOrDefault()?.ToDomain();
    }

    public async Task<IReadOnlyList<IngestionRunIndexRecord>> ListRunsAsync(
        string? repositoryId = null,
        int limit = 50,
        CancellationToken cancellationToken = default)
    {
        var filter = string.IsNullOrWhiteSpace(repositoryId)
            ? Builders<IngestionRunDocument>.Filter.Empty
            : Builders<IngestionRunDocument>.Filter.Eq(item => item.RepositoryId, repositoryId);
        var documents = await _runs
            .Find(filter)
            .SortByDescending(item => item.StartedAtUtc)
            .Limit(Math.Clamp(limit, 1, 500))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);

        return documents.Select(document => document.ToDomain()).ToArray();
    }

    public async Task DeleteRepositoryAsync(
        string repositoryId,
        CancellationToken cancellationToken = default)
    {
        var repositoryFilter = Builders<RepositoryDocument>.Filter.Eq(item => item.RepositoryId, repositoryId);
        var runsFilter = Builders<IngestionRunDocument>.Filter.Eq(item => item.RepositoryId, repositoryId);

        await _repositories.DeleteOneAsync(repositoryFilter, cancellationToken)
            .ConfigureAwait(false);
        await _runs.DeleteManyAsync(runsFilter, cancellationToken)
            .ConfigureAwait(false);
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
                "MongoDB registry store is available.",
                new Dictionary<string, string>
                {
                    ["database"] = _database.DatabaseNamespace.DatabaseName,
                    ["repositoriesCollection"] = _repositories.CollectionNamespace.CollectionName,
                    ["runsCollection"] = _runs.CollectionNamespace.CollectionName
                });
        }
        catch (Exception exception) when (exception is MongoException or TimeoutException)
        {
            return new ComponentHealth(
                Name,
                ComponentState.Degraded,
                "MongoDB registry store is not reachable.",
                new Dictionary<string, string>
                {
                    ["database"] = _database.DatabaseNamespace.DatabaseName,
                    ["repositoriesCollection"] = _repositories.CollectionNamespace.CollectionName,
                    ["runsCollection"] = _runs.CollectionNamespace.CollectionName,
                    ["detail"] = exception.Message
                });
        }
    }

    private static IMongoClient CreateClient(MongoRegistryStoreOptions options)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(options.ConnectionString);
        ArgumentException.ThrowIfNullOrWhiteSpace(options.DatabaseName);

        var settings = MongoClientSettings.FromConnectionString(options.ConnectionString);
        settings.ServerSelectionTimeout = options.ServerSelectionTimeout ?? TimeSpan.FromSeconds(2);

        return new MongoClient(settings);
    }

    private sealed class RepositoryDocument
    {
        [BsonId]
        [BsonElement("_id")]
        public required string RepositoryId { get; init; }

        [BsonElement("rootPath")]
        public required string RootPath { get; set; }

        [BsonElement("alias")]
        public string? Alias { get; set; }

        [BsonElement("remoteUrl")]
        public string? RemoteUrl { get; set; }

        [BsonElement("branch")]
        public string? Branch { get; set; }

        [BsonElement("commit")]
        public string? Commit { get; set; }

        [BsonElement("firstSeenAtUtc")]
        public required DateTime FirstSeenAtUtc { get; set; }

        [BsonElement("lastSeenAtUtc")]
        public required DateTime LastSeenAtUtc { get; set; }

        [BsonElement("lastRunId")]
        public string? LastRunId { get; set; }

        [BsonElement("lastStage")]
        public string? LastStage { get; set; }

        [BsonElement("lastMessage")]
        public string? LastMessage { get; set; }

        [BsonElement("nodeCount")]
        public int NodeCount { get; set; }

        [BsonElement("relationshipCount")]
        public int RelationshipCount { get; set; }

        [BsonElement("contentCount")]
        public int ContentCount { get; set; }

        [BsonElement("embeddingCount")]
        public int? EmbeddingCount { get; set; }

        [BsonElement("metadata")]
        public Dictionary<string, string> Metadata { get; set; } = new(StringComparer.Ordinal);

        public RepositoryIndexRecord ToDomain()
        {
            return new RepositoryIndexRecord(
                RepositoryId,
                RootPath,
                RemoteUrl,
                Branch,
                Commit,
                DateTimeOffsetFromUtc(FirstSeenAtUtc),
                DateTimeOffsetFromUtc(LastSeenAtUtc),
                LastRunId,
                ParseStage(LastStage),
                LastMessage,
                NodeCount,
                RelationshipCount,
                ContentCount,
                EmbeddingCount,
                Metadata,
                Alias ?? MetadataAlias(Metadata));
        }
    }

    private sealed class IngestionRunDocument
    {
        [BsonId]
        [BsonElement("_id")]
        public required string RunId { get; init; }

        [BsonElement("repositoryId")]
        public required string RepositoryId { get; init; }

        [BsonElement("repositoryRoot")]
        public required string RepositoryRoot { get; init; }

        [BsonElement("stage")]
        public required string Stage { get; init; }

        [BsonElement("startedAtUtc")]
        public required DateTime StartedAtUtc { get; init; }

        [BsonElement("finishedAtUtc")]
        public DateTime? FinishedAtUtc { get; init; }

        [BsonElement("message")]
        public string? Message { get; init; }

        [BsonElement("language")]
        public required string Language { get; init; }

        [BsonElement("parserName")]
        public required string ParserName { get; init; }

        [BsonElement("solutionPath")]
        public string? SolutionPath { get; init; }

        [BsonElement("projectPath")]
        public string? ProjectPath { get; init; }

        [BsonElement("dryRun")]
        public bool DryRun { get; init; }

        [BsonElement("skipEmbeddings")]
        public bool SkipEmbeddings { get; init; }

        [BsonElement("embeddingProvider")]
        public required string EmbeddingProvider { get; init; }

        [BsonElement("embeddingModel")]
        public required string EmbeddingModel { get; init; }

        [BsonElement("nodeCount")]
        public int NodeCount { get; init; }

        [BsonElement("relationshipCount")]
        public int RelationshipCount { get; init; }

        [BsonElement("contentCount")]
        public int ContentCount { get; init; }

        [BsonElement("embeddingCount")]
        public int EmbeddingCount { get; init; }

        [BsonElement("stats")]
        public IngestionStatsDocument? Stats { get; init; }

        [BsonElement("diagnosticCount")]
        public int DiagnosticCount { get; init; }

        [BsonElement("errorDiagnosticCount")]
        public int ErrorDiagnosticCount { get; init; }

        [BsonElement("warningDiagnosticCount")]
        public int WarningDiagnosticCount { get; init; }

        [BsonElement("metadata")]
        public Dictionary<string, string> Metadata { get; init; } = new(StringComparer.Ordinal);

        public static IngestionRunDocument FromDomain(IngestionRunIndexRecord run)
        {
            return new IngestionRunDocument
            {
                RunId = run.RunId,
                RepositoryId = run.RepositoryId,
                RepositoryRoot = run.RepositoryRoot,
                Stage = run.Stage.ToString(),
                StartedAtUtc = run.StartedAt.UtcDateTime,
                FinishedAtUtc = run.FinishedAt?.UtcDateTime,
                Message = run.Message,
                Language = run.Language,
                ParserName = run.ParserName,
                SolutionPath = run.SolutionPath,
                ProjectPath = run.ProjectPath,
                DryRun = run.DryRun,
                SkipEmbeddings = run.SkipEmbeddings,
                EmbeddingProvider = run.EmbeddingProvider,
                EmbeddingModel = run.EmbeddingModel,
                NodeCount = run.NodeCount,
                RelationshipCount = run.RelationshipCount,
                ContentCount = run.ContentCount,
                EmbeddingCount = run.EmbeddingCount,
                Stats = run.Stats is null ? null : IngestionStatsDocument.FromDomain(run.Stats),
                DiagnosticCount = run.DiagnosticCount,
                ErrorDiagnosticCount = run.ErrorDiagnosticCount,
                WarningDiagnosticCount = run.WarningDiagnosticCount,
                Metadata = new Dictionary<string, string>(run.Metadata, StringComparer.Ordinal)
            };
        }

        public IngestionRunIndexRecord ToDomain()
        {
            return new IngestionRunIndexRecord(
                RunId,
                RepositoryId,
                RepositoryRoot,
                ParseStage(Stage) ?? IngestionStage.Failed,
                DateTimeOffsetFromUtc(StartedAtUtc),
                FinishedAtUtc is null ? null : DateTimeOffsetFromUtc(FinishedAtUtc.Value),
                Message,
                Language,
                ParserName,
                SolutionPath,
                ProjectPath,
                DryRun,
                SkipEmbeddings,
                EmbeddingProvider,
                EmbeddingModel,
                NodeCount,
                RelationshipCount,
                ContentCount,
                EmbeddingCount,
                Stats?.ToDomain(),
                DiagnosticCount,
                ErrorDiagnosticCount,
                WarningDiagnosticCount,
                Metadata);
        }
    }

    private sealed record IngestionStatsDocument(
        int ParsedNodeCount,
        int WrittenNodeCount,
        int SkippedNodeCount,
        int ParsedRelationshipCount,
        int WrittenRelationshipCount,
        int SkippedRelationshipCount,
        int ParsedContentCount,
        int WrittenContentCount,
        int SkippedContentCount,
        int WrittenEmbeddingCount,
        int SkippedEmbeddingCount)
    {
        public static IngestionStatsDocument FromDomain(IngestionStats stats)
        {
            return new IngestionStatsDocument(
                stats.ParsedNodeCount,
                stats.WrittenNodeCount,
                stats.SkippedNodeCount,
                stats.ParsedRelationshipCount,
                stats.WrittenRelationshipCount,
                stats.SkippedRelationshipCount,
                stats.ParsedContentCount,
                stats.WrittenContentCount,
                stats.SkippedContentCount,
                stats.WrittenEmbeddingCount,
                stats.SkippedEmbeddingCount);
        }

        public IngestionStats ToDomain()
        {
            return new IngestionStats(
                ParsedNodeCount,
                WrittenNodeCount,
                SkippedNodeCount,
                ParsedRelationshipCount,
                WrittenRelationshipCount,
                SkippedRelationshipCount,
                ParsedContentCount,
                WrittenContentCount,
                SkippedContentCount,
                WrittenEmbeddingCount,
                SkippedEmbeddingCount);
        }
    }

    private static IngestionStage? ParseStage(string? stage)
    {
        return Enum.TryParse<IngestionStage>(stage, ignoreCase: true, out var parsed)
            ? parsed
            : null;
    }

    private static DateTimeOffset DateTimeOffsetFromUtc(DateTime value)
    {
        return new DateTimeOffset(DateTime.SpecifyKind(value, DateTimeKind.Utc));
    }

    private static string? MetadataAlias(IReadOnlyDictionary<string, string> metadata)
    {
        return metadata.TryGetValue("alias", out var alias) ? alias : null;
    }
}
