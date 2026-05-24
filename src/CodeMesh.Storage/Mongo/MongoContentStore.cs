using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Health;
using MongoDB.Bson.Serialization.Attributes;
using MongoDB.Driver;

namespace CodeMesh.Storage.Mongo;

public sealed record MongoContentStoreOptions(
    string ConnectionString,
    string DatabaseName,
    string CollectionName = "content",
    TimeSpan? ServerSelectionTimeout = null);

public sealed class MongoContentStore : IContentStore, IRefreshableContentStore, IStoreHealthCheck
{
    private readonly IMongoDatabase _database;
    private readonly IMongoCollection<ContentDocument> _contents;

    public MongoContentStore(MongoContentStoreOptions options)
        : this(CreateClient(options), options.DatabaseName, options.CollectionName)
    {
    }

    public MongoContentStore(IMongoClient client, string databaseName, string collectionName = "content")
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(databaseName);
        ArgumentException.ThrowIfNullOrWhiteSpace(collectionName);

        _database = client.GetDatabase(databaseName);
        _contents = _database.GetCollection<ContentDocument>(collectionName);
        Name = $"mongodb:{databaseName}.{collectionName}";
    }

    public string Name { get; }

    public async Task UpsertContentAsync(CodeContent content, CancellationToken cancellationToken = default)
    {
        var document = ContentDocument.FromDomain(content);
        var filter = Builders<ContentDocument>.Filter.Eq(item => item.Hash, content.Hash);
        var options = new ReplaceOptions { IsUpsert = true };

        await _contents.ReplaceOneAsync(filter, document, options, cancellationToken)
            .ConfigureAwait(false);
    }

    public async Task UpsertContentAsync(
        CodeContent content,
        RepositoryRef repository,
        string ingestionRunId,
        DateTimeOffset seenAt,
        CancellationToken cancellationToken = default)
    {
        var filter = Builders<ContentDocument>.Filter.Eq(item => item.Hash, content.Hash);
        var update = Builders<ContentDocument>.Update
            .SetOnInsert(item => item.Hash, content.Hash)
            .SetOnInsert(item => item.CreatedAtUtc, content.CreatedAt.UtcDateTime)
            .Set(item => item.Text, content.Text)
            .Set(item => item.MediaType, content.MediaType)
            .Set(item => item.UpdatedAtUtc, content.UpdatedAt.UtcDateTime)
            .AddToSet("repositoryIds", repository.Id)
            .Set($"repositoryRuns.{repository.Id}", ingestionRunId)
            .Set($"repositoryLastSeenAtUtc.{repository.Id}", seenAt.UtcDateTime);
        var options = new UpdateOptions { IsUpsert = true };

        await _contents.UpdateOneAsync(filter, update, options, cancellationToken)
            .ConfigureAwait(false);
    }

    public async Task<CodeContent?> GetContentAsync(
        string contentHash,
        CancellationToken cancellationToken = default)
    {
        var filter = Builders<ContentDocument>.Filter.Eq(item => item.Hash, contentHash);
        var document = await _contents
            .Find(filter)
            .FirstOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);

        return document?.ToDomain();
    }

    public async Task RemoveStaleContentAsync(
        string repositoryId,
        string ingestionRunId,
        CancellationToken cancellationToken = default)
    {
        var staleFilter =
            Builders<ContentDocument>.Filter.Exists($"repositoryRuns.{repositoryId}") &
            Builders<ContentDocument>.Filter.Ne($"repositoryRuns.{repositoryId}", ingestionRunId);
        var removeRepository = Builders<ContentDocument>.Update
            .Pull("repositoryIds", repositoryId)
            .Unset($"repositoryRuns.{repositoryId}")
            .Unset($"repositoryLastSeenAtUtc.{repositoryId}");

        await _contents.UpdateManyAsync(staleFilter, removeRepository, cancellationToken: cancellationToken)
            .ConfigureAwait(false);

        var unreferencedFilter = Builders<ContentDocument>.Filter.Size("repositoryIds", 0);
        await _contents.DeleteManyAsync(unreferencedFilter, cancellationToken)
            .ConfigureAwait(false);
    }

    public async Task<ComponentHealth> CheckAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            var command = new MongoDB.Bson.BsonDocument("ping", 1);
            await _database.RunCommandAsync<MongoDB.Bson.BsonDocument>(command, cancellationToken: cancellationToken)
                .ConfigureAwait(false);

            var metadata = new Dictionary<string, string>
            {
                ["database"] = _database.DatabaseNamespace.DatabaseName,
                ["collection"] = _contents.CollectionNamespace.CollectionName
            };

            return new ComponentHealth(
                Name,
                ComponentState.Healthy,
                "MongoDB content store is available.",
                metadata);
        }
        catch (Exception exception) when (exception is MongoException or TimeoutException)
        {
            return new ComponentHealth(
                Name,
                ComponentState.Degraded,
                "MongoDB content store is not reachable.",
                new Dictionary<string, string>
                {
                    ["database"] = _database.DatabaseNamespace.DatabaseName,
                    ["collection"] = _contents.CollectionNamespace.CollectionName,
                    ["detail"] = exception.Message
                });
        }
    }

    private static IMongoClient CreateClient(MongoContentStoreOptions options)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(options.ConnectionString);
        ArgumentException.ThrowIfNullOrWhiteSpace(options.DatabaseName);

        var settings = MongoClientSettings.FromConnectionString(options.ConnectionString);
        settings.ServerSelectionTimeout = options.ServerSelectionTimeout ?? TimeSpan.FromSeconds(2);

        return new MongoClient(settings);
    }

    private sealed class ContentDocument
    {
        [BsonId]
        [BsonElement("_id")]
        public required string Hash { get; init; }

        [BsonElement("text")]
        public required string Text { get; init; }

        [BsonElement("mediaType")]
        public required string MediaType { get; init; }

        [BsonElement("createdAtUtc")]
        public required DateTime CreatedAtUtc { get; init; }

        [BsonElement("updatedAtUtc")]
        public required DateTime UpdatedAtUtc { get; set; }

        [BsonElement("repositoryIds")]
        public List<string> RepositoryIds { get; set; } = [];

        [BsonElement("repositoryRuns")]
        public Dictionary<string, string> RepositoryRuns { get; set; } = new(StringComparer.Ordinal);

        [BsonElement("repositoryLastSeenAtUtc")]
        public Dictionary<string, DateTime> RepositoryLastSeenAtUtc { get; set; } = new(StringComparer.Ordinal);

        public static ContentDocument FromDomain(CodeContent content)
        {
            return new ContentDocument
            {
                Hash = content.Hash,
                Text = content.Text,
                MediaType = content.MediaType,
                CreatedAtUtc = content.CreatedAt.UtcDateTime,
                UpdatedAtUtc = content.UpdatedAt.UtcDateTime,
                RepositoryIds = [],
                RepositoryRuns = new Dictionary<string, string>(StringComparer.Ordinal),
                RepositoryLastSeenAtUtc = new Dictionary<string, DateTime>(StringComparer.Ordinal)
            };
        }

        public CodeContent ToDomain()
        {
            return new CodeContent(
                Hash,
                Text,
                MediaType,
                new DateTimeOffset(DateTime.SpecifyKind(CreatedAtUtc, DateTimeKind.Utc)),
                new DateTimeOffset(DateTime.SpecifyKind(UpdatedAtUtc, DateTimeKind.Utc)));
        }
    }
}
