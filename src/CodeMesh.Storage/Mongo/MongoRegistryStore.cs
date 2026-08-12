using CodeMesh.Domain.Contracts;
using CodeMesh.Domain.Health;
using CodeMesh.Domain.Utilities;
using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;
using MongoDB.Driver;

namespace CodeMesh.Storage.Mongo;

public sealed record MongoRegistryStoreOptions(
    string ConnectionString,
    string DatabaseName,
    string RepositoriesCollectionName = "repositories",
    string RunsCollectionName = "ingestion_runs",
    TimeSpan? ServerSelectionTimeout = null,
    string ProjectsCollectionName = "snapshot_projects",
    string CheckoutsCollectionName = "snapshot_checkouts",
    string SnapshotsCollectionName = "snapshots",
    string GenerationsCollectionName = "ingestion_generations",
    string ObservationsCollectionName = "snapshot_observations");

public sealed class MongoRegistryStore : ISnapshotRegistryStore, IStoreHealthCheck
{
    private readonly IMongoDatabase _database;
    private readonly IMongoCollection<RepositoryDocument> _repositories;
    private readonly IMongoCollection<IngestionRunDocument> _runs;
    private readonly IMongoCollection<BsonDocument> _projects;
    private readonly IMongoCollection<BsonDocument> _checkouts;
    private readonly IMongoCollection<BsonDocument> _snapshots;
    private readonly IMongoCollection<BsonDocument> _generations;
    private readonly IMongoCollection<BsonDocument> _observations;

    public MongoRegistryStore(MongoRegistryStoreOptions options)
        : this(
            CreateClient(options),
            options.DatabaseName,
            options.RepositoriesCollectionName,
            options.RunsCollectionName,
            options.ProjectsCollectionName,
            options.CheckoutsCollectionName,
            options.SnapshotsCollectionName,
            options.GenerationsCollectionName,
            options.ObservationsCollectionName)
    {
    }

    public MongoRegistryStore(
        IMongoClient client,
        string databaseName,
        string repositoriesCollectionName = "repositories",
        string runsCollectionName = "ingestion_runs",
        string projectsCollectionName = "snapshot_projects",
        string checkoutsCollectionName = "snapshot_checkouts",
        string snapshotsCollectionName = "snapshots",
        string generationsCollectionName = "ingestion_generations",
        string observationsCollectionName = "snapshot_observations")
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(databaseName);
        ArgumentException.ThrowIfNullOrWhiteSpace(repositoriesCollectionName);
        ArgumentException.ThrowIfNullOrWhiteSpace(runsCollectionName);

        _database = client.GetDatabase(databaseName);
        _repositories = _database.GetCollection<RepositoryDocument>(repositoriesCollectionName);
        _runs = _database.GetCollection<IngestionRunDocument>(runsCollectionName);
        _projects = _database.GetCollection<BsonDocument>(projectsCollectionName);
        _checkouts = _database.GetCollection<BsonDocument>(checkoutsCollectionName);
        _snapshots = _database.GetCollection<BsonDocument>(snapshotsCollectionName);
        _generations = _database.GetCollection<BsonDocument>(generationsCollectionName);
        _observations = _database.GetCollection<BsonDocument>(observationsCollectionName);
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
        await _projects.DeleteOneAsync(Builders<BsonDocument>.Filter.Eq("_id", repositoryId), cancellationToken)
            .ConfigureAwait(false);
        await _checkouts.DeleteManyAsync(Builders<BsonDocument>.Filter.Eq("projectId", repositoryId), cancellationToken)
            .ConfigureAwait(false);
        await _snapshots.DeleteManyAsync(Builders<BsonDocument>.Filter.Eq("projectId", repositoryId), cancellationToken)
            .ConfigureAwait(false);
        await _generations.DeleteManyAsync(Builders<BsonDocument>.Filter.Eq("projectId", repositoryId), cancellationToken)
            .ConfigureAwait(false);
        await _observations.DeleteManyAsync(Builders<BsonDocument>.Filter.Eq("projectId", repositoryId), cancellationToken)
            .ConfigureAwait(false);
    }

    public async Task<CheckoutIdentityRecord?> GetCheckoutAsync(
        string checkoutId,
        CancellationToken cancellationToken = default)
    {
        var document = await _checkouts
            .Find(Builders<BsonDocument>.Filter.Eq("_id", checkoutId))
            .FirstOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);
        return document is null ? null : CheckoutFromDocument(document);
    }

    public async Task UpsertCheckoutAsync(
        CheckoutIdentityRecord checkout,
        CancellationToken cancellationToken = default)
    {
        await _checkouts.ReplaceOneAsync(
                Builders<BsonDocument>.Filter.Eq("_id", checkout.CheckoutId),
                CheckoutDocument(checkout),
                new ReplaceOptions { IsUpsert = true },
                cancellationToken)
            .ConfigureAwait(false);
    }

    public async Task<SnapshotIndexRecord?> GetSnapshotAsync(
        string snapshotId,
        CancellationToken cancellationToken = default)
    {
        var document = await _snapshots
            .Find(Builders<BsonDocument>.Filter.Eq("_id", snapshotId))
            .FirstOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);
        return document is null ? null : SnapshotFromDocument(document);
    }

    public async Task<IReadOnlyList<SnapshotIndexRecord>> ListSnapshotsAsync(
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var documents = await _snapshots
            .Find(Builders<BsonDocument>.Filter.Eq("projectId", projectId))
            .Sort(Builders<BsonDocument>.Sort.Descending("lastReferencedAtUtc"))
            .ToListAsync(cancellationToken)
            .ConfigureAwait(false);
        return documents.Select(SnapshotFromDocument).ToArray();
    }

    public async Task<IReadOnlyList<SnapshotSlotRecord>> ListSlotsAsync(
        string projectId,
        CancellationToken cancellationToken = default)
    {
        var document = await _projects
            .Find(Builders<BsonDocument>.Filter.Eq("_id", projectId))
            .FirstOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);
        return SlotsFromProjectDocument(document);
    }

    public async Task StageGenerationAsync(
        IngestionGenerationRecord generation,
        SnapshotIndexRecord snapshot,
        CancellationToken cancellationToken = default)
    {
        await _generations.ReplaceOneAsync(
                Builders<BsonDocument>.Filter.Eq("_id", generation.GenerationId),
                GenerationDocument(generation),
                new ReplaceOptions { IsUpsert = true },
                cancellationToken)
            .ConfigureAwait(false);
        var existing = await GetSnapshotAsync(snapshot.SnapshotId, cancellationToken).ConfigureAwait(false);
        if (existing?.State != SnapshotState.Active)
        {
            await _snapshots.ReplaceOneAsync(
                    Builders<BsonDocument>.Filter.Eq("_id", snapshot.SnapshotId),
                    SnapshotDocument(snapshot),
                    new ReplaceOptions { IsUpsert = true },
                    cancellationToken)
                .ConfigureAwait(false);
        }
    }

    public async Task<SnapshotPublicationResult> PublishSnapshotAsync(
        SnapshotPublication publication,
        CancellationToken cancellationToken = default)
    {
        var filter = Builders<BsonDocument>.Filter.Eq("_id", publication.Project.ProjectId);
        var current = await _projects.Find(filter).FirstOrDefaultAsync(cancellationToken).ConfigureAwait(false);
        var revision = current?.GetValue("revision", 0L).ToInt64() ?? 0L;
        var slots = SlotsFromProjectDocument(current).ToDictionary(slot => slot.SlotId, StringComparer.Ordinal);

        foreach (var expected in publication.ExpectedSlots)
        {
            slots.TryGetValue(expected.SlotId, out var actual);
            if (!string.Equals(actual?.SnapshotId, expected.SnapshotId, StringComparison.Ordinal) ||
                actual?.Version != expected.Version)
            {
                return new SnapshotPublicationResult(false, Array.Empty<SnapshotSlotRecord>(), Array.Empty<string>(), $"Slot '{expected.SlotId}' changed during ingestion.");
            }
        }

        var now = publication.Observation.ObservedAt;
        var publishedSlots = new List<SnapshotSlotRecord>();
        foreach (var requested in publication.Slots)
        {
            slots.TryGetValue(requested.SlotId, out var previous);
            var published = requested with { Version = (previous?.Version ?? 0) + 1, UpdatedAt = now };
            slots[published.SlotId] = published;
            publishedSlots.Add(published);
        }

        await UpsertCheckoutAsync(publication.Checkout, cancellationToken).ConfigureAwait(false);
        await _observations.ReplaceOneAsync(
                Builders<BsonDocument>.Filter.Eq("_id", publication.Observation.ObservationId),
                ObservationDocument(publication.Observation),
                new ReplaceOptions { IsUpsert = true },
                cancellationToken)
            .ConfigureAwait(false);
        await _generations.ReplaceOneAsync(
                Builders<BsonDocument>.Filter.Eq("_id", publication.Generation.GenerationId),
                GenerationDocument(publication.Generation with { State = IngestionGenerationState.Published, FinishedAt = now, Error = null }),
                new ReplaceOptions { IsUpsert = true },
                cancellationToken)
            .ConfigureAwait(false);
        await _snapshots.ReplaceOneAsync(
                Builders<BsonDocument>.Filter.Eq("_id", publication.Snapshot.SnapshotId),
                SnapshotDocument(publication.Snapshot with { State = SnapshotState.Active, LastReferencedAt = now, CollectibleAfter = null }),
                new ReplaceOptions { IsUpsert = true },
                cancellationToken)
            .ConfigureAwait(false);

        var referenced = slots.Values.Select(slot => slot.SnapshotId).ToHashSet(StringComparer.Ordinal);
        var projectSnapshots = await ListSnapshotsAsync(publication.Project.ProjectId, cancellationToken).ConfigureAwait(false);
        var newlyCollectible = projectSnapshots
            .Where(snapshot => snapshot.State == SnapshotState.Active && !referenced.Contains(snapshot.SnapshotId))
            .Select(snapshot => snapshot.SnapshotId)
            .ToArray();
        if (newlyCollectible.Length > 0)
        {
            var collectibleFilter = Builders<BsonDocument>.Filter.In("_id", newlyCollectible);
            var collectibleUpdate = Builders<BsonDocument>.Update
                .Set("state", SnapshotState.Collectible.ToString())
                .Set("collectibleAfterUtc", (now + publication.UnreferencedGracePeriod).UtcDateTime);
            await _snapshots.UpdateManyAsync(collectibleFilter, collectibleUpdate, cancellationToken: cancellationToken)
                .ConfigureAwait(false);
        }

        var replacement = new BsonDocument
        {
            ["_id"] = publication.Project.ProjectId,
            ["revision"] = revision + 1,
            ["alias"] = publication.Project.Alias,
            ["remoteUrl"] = BsonValue.Create(publication.Project.RemoteUrl),
            ["createdAtUtc"] = publication.Project.CreatedAt.UtcDateTime,
            ["lastSeenAtUtc"] = publication.Project.LastSeenAt.UtcDateTime,
            ["slots"] = new BsonArray(slots.Values.OrderBy(slot => slot.SlotId, StringComparer.Ordinal).Select(SlotDocument))
        };
        var casFilter = revision == 0 && current is null
            ? filter & Builders<BsonDocument>.Filter.Exists("revision", false)
            : filter & Builders<BsonDocument>.Filter.Eq("revision", revision);
        ReplaceOneResult replaceResult;
        try
        {
            replaceResult = await _projects.ReplaceOneAsync(
                    casFilter,
                    replacement,
                    new ReplaceOptions { IsUpsert = current is null },
                    cancellationToken)
                .ConfigureAwait(false);
        }
        catch (MongoWriteException exception) when (exception.WriteError?.Category == ServerErrorCategory.DuplicateKey)
        {
            return new SnapshotPublicationResult(false, Array.Empty<SnapshotSlotRecord>(), Array.Empty<string>(), "Project slots changed during ingestion.");
        }
        if (replaceResult.MatchedCount == 0 && replaceResult.UpsertedId is null)
        {
            return new SnapshotPublicationResult(false, Array.Empty<SnapshotSlotRecord>(), Array.Empty<string>(), "Project slots changed during ingestion.");
        }

        return new SnapshotPublicationResult(true, publishedSlots, newlyCollectible, null);
    }

    public async Task MarkGenerationFailedAsync(
        string generationId,
        string error,
        CancellationToken cancellationToken = default)
    {
        var generation = await _generations
            .Find(Builders<BsonDocument>.Filter.Eq("_id", generationId))
            .FirstOrDefaultAsync(cancellationToken)
            .ConfigureAwait(false);
        if (generation is null)
        {
            return;
        }

        await _generations.UpdateOneAsync(
                Builders<BsonDocument>.Filter.Eq("_id", generationId),
                Builders<BsonDocument>.Update
                    .Set("state", IngestionGenerationState.Failed.ToString())
                    .Set("finishedAtUtc", DateTime.UtcNow)
                    .Set("error", error),
                cancellationToken: cancellationToken)
            .ConfigureAwait(false);
        var snapshotId = generation.GetValue("snapshotId", "").AsString;
        var projectId = generation.GetValue("projectId", "").AsString;
        var slots = await ListSlotsAsync(projectId, cancellationToken).ConfigureAwait(false);
        if (!slots.Any(slot => string.Equals(slot.SnapshotId, snapshotId, StringComparison.Ordinal)))
        {
            await _snapshots.UpdateOneAsync(
                    Builders<BsonDocument>.Filter.Eq("_id", snapshotId),
                    Builders<BsonDocument>.Update
                        .Set("state", SnapshotState.Failed.ToString())
                        .Set("collectibleAfterUtc", DateTime.UtcNow),
                    cancellationToken: cancellationToken)
                .ConfigureAwait(false);
        }
    }

    public async Task<IReadOnlyList<SnapshotIndexRecord>> ListCollectibleSnapshotsAsync(
        DateTimeOffset now,
        CancellationToken cancellationToken = default)
    {
        var stateFilter = Builders<BsonDocument>.Filter.In("state", [SnapshotState.Collectible.ToString(), SnapshotState.Failed.ToString()]);
        var timeFilter = Builders<BsonDocument>.Filter.Lte("collectibleAfterUtc", now.UtcDateTime) |
            Builders<BsonDocument>.Filter.Exists("collectibleAfterUtc", false) |
            Builders<BsonDocument>.Filter.Eq("collectibleAfterUtc", BsonNull.Value);
        var documents = await _snapshots.Find(stateFilter & timeFilter).ToListAsync(cancellationToken).ConfigureAwait(false);
        var referenced = new HashSet<string>(StringComparer.Ordinal);
        var projectDocuments = await _projects.Find(Builders<BsonDocument>.Filter.Empty).ToListAsync(cancellationToken).ConfigureAwait(false);
        foreach (var project in projectDocuments)
        {
            referenced.UnionWith(SlotsFromProjectDocument(project).Select(slot => slot.SnapshotId));
        }

        return documents.Select(SnapshotFromDocument).Where(snapshot => !referenced.Contains(snapshot.SnapshotId)).ToArray();
    }

    public async Task DeleteSnapshotRecordAsync(
        string snapshotId,
        CancellationToken cancellationToken = default)
    {
        var projectDocuments = await _projects.Find(Builders<BsonDocument>.Filter.Empty).ToListAsync(cancellationToken).ConfigureAwait(false);
        if (projectDocuments.SelectMany(SlotsFromProjectDocument).Any(slot => string.Equals(slot.SnapshotId, snapshotId, StringComparison.Ordinal)))
        {
            throw new InvalidOperationException($"Snapshot '{snapshotId}' is still referenced by an active slot.");
        }

        await _snapshots.DeleteOneAsync(Builders<BsonDocument>.Filter.Eq("_id", snapshotId), cancellationToken).ConfigureAwait(false);
    }

    public async Task<SnapshotSlotRecord?> ResolveSlotAsync(
        string projectId,
        SnapshotSlotKind kind,
        string key,
        CancellationToken cancellationToken = default)
    {
        return (await ListSlotsAsync(projectId, cancellationToken).ConfigureAwait(false))
            .SingleOrDefault(slot => slot.Kind == kind && string.Equals(slot.Key, key, StringComparison.Ordinal));
    }

    public async Task MigrateLegacyRepositoryAsync(
        string legacyRepositoryId,
        string projectId,
        CancellationToken cancellationToken = default)
    {
        if (string.Equals(legacyRepositoryId, projectId, StringComparison.Ordinal))
        {
            return;
        }

        await _runs.UpdateManyAsync(
                Builders<IngestionRunDocument>.Filter.Eq(item => item.RepositoryId, legacyRepositoryId),
                Builders<IngestionRunDocument>.Update.Set(item => item.RepositoryId, projectId),
                cancellationToken: cancellationToken)
            .ConfigureAwait(false);
        await _repositories.DeleteOneAsync(
                Builders<RepositoryDocument>.Filter.Eq(item => item.RepositoryId, legacyRepositoryId),
                cancellationToken)
            .ConfigureAwait(false);
    }

    public async Task<SnapshotSlotMutationResult> UpsertRetainedSlotAsync(
        string projectId,
        SnapshotSlotKind kind,
        string key,
        string snapshotId,
        long? expectedVersion,
        CancellationToken cancellationToken = default)
    {
        var snapshot = await GetSnapshotAsync(snapshotId, cancellationToken).ConfigureAwait(false);
        if (snapshot is null || !string.Equals(snapshot.ProjectId, projectId, StringComparison.Ordinal))
        {
            return new SnapshotSlotMutationResult(false, null, Array.Empty<string>(), "Snapshot was not found in the project.");
        }

        return await MutateSlotAsync(
                projectId,
                kind,
                key,
                expectedVersion,
                current => new SnapshotSlotRecord(
                    RetainedSlotId(projectId, kind, key),
                    projectId,
                    kind,
                    key,
                    snapshotId,
                    (current?.Version ?? 0) + 1,
                    DateTimeOffset.UtcNow),
                TimeSpan.Zero,
                cancellationToken)
            .ConfigureAwait(false);
    }

    public Task<SnapshotSlotMutationResult> DeleteSlotAsync(
        string projectId,
        SnapshotSlotKind kind,
        string key,
        long? expectedVersion,
        TimeSpan unreferencedGracePeriod,
        CancellationToken cancellationToken = default)
    {
        return MutateSlotAsync(
            projectId,
            kind,
            key,
            expectedVersion,
            _ => null,
            unreferencedGracePeriod,
            cancellationToken);
    }

    private async Task<SnapshotSlotMutationResult> MutateSlotAsync(
        string projectId,
        SnapshotSlotKind kind,
        string key,
        long? expectedVersion,
        Func<SnapshotSlotRecord?, SnapshotSlotRecord?> mutation,
        TimeSpan unreferencedGracePeriod,
        CancellationToken cancellationToken)
    {
        var filter = Builders<BsonDocument>.Filter.Eq("_id", projectId);
        var project = await _projects.Find(filter).FirstOrDefaultAsync(cancellationToken).ConfigureAwait(false);
        if (project is null)
        {
            return new SnapshotSlotMutationResult(false, null, Array.Empty<string>(), "Project was not found.");
        }

        var revision = project.GetValue("revision", 0L).ToInt64();
        var slots = SlotsFromProjectDocument(project).ToDictionary(slot => slot.SlotId, StringComparer.Ordinal);
        var slotId = RetainedSlotId(projectId, kind, key);
        slots.TryGetValue(slotId, out var current);
        if (expectedVersion.HasValue && current?.Version != expectedVersion)
        {
            return new SnapshotSlotMutationResult(false, current, Array.Empty<string>(), $"Slot '{slotId}' changed.");
        }

        var changed = mutation(current);
        if (changed is null)
        {
            if (current is null)
            {
                return new SnapshotSlotMutationResult(false, null, Array.Empty<string>(), null);
            }
            slots.Remove(slotId);
        }
        else
        {
            slots[slotId] = changed;
        }

        var replacement = new BsonDocument(project)
        {
            ["revision"] = revision + 1,
            ["slots"] = new BsonArray(slots.Values.OrderBy(slot => slot.SlotId, StringComparer.Ordinal).Select(SlotDocument))
        };
        var result = await _projects.ReplaceOneAsync(
                filter & Builders<BsonDocument>.Filter.Eq("revision", revision),
                replacement,
                cancellationToken: cancellationToken)
            .ConfigureAwait(false);
        if (result.MatchedCount == 0)
        {
            return new SnapshotSlotMutationResult(false, current, Array.Empty<string>(), "Project slots changed.");
        }

        var newlyCollectible = Array.Empty<string>();
        if (changed is not null)
        {
            await _snapshots.UpdateOneAsync(
                    Builders<BsonDocument>.Filter.Eq("_id", changed.SnapshotId),
                    Builders<BsonDocument>.Update
                        .Set("state", SnapshotState.Active.ToString())
                        .Set("lastReferencedAtUtc", changed.UpdatedAt.UtcDateTime)
                        .Unset("collectibleAfterUtc"),
                    cancellationToken: cancellationToken)
                .ConfigureAwait(false);
        }
        else if (current is not null && !slots.Values.Any(slot => string.Equals(slot.SnapshotId, current.SnapshotId, StringComparison.Ordinal)))
        {
            newlyCollectible = [current.SnapshotId];
            await _snapshots.UpdateOneAsync(
                    Builders<BsonDocument>.Filter.Eq("_id", current.SnapshotId),
                    Builders<BsonDocument>.Update
                        .Set("state", SnapshotState.Collectible.ToString())
                        .Set("collectibleAfterUtc", (DateTimeOffset.UtcNow + unreferencedGracePeriod).UtcDateTime),
                    cancellationToken: cancellationToken)
                .ConfigureAwait(false);
        }

        return new SnapshotSlotMutationResult(true, changed ?? current, newlyCollectible, null);
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

    private static BsonDocument CheckoutDocument(CheckoutIdentityRecord checkout)
    {
        return new BsonDocument
        {
            ["_id"] = checkout.CheckoutId,
            ["projectId"] = checkout.ProjectId,
            ["rootPath"] = checkout.RootPath,
            ["createdAtUtc"] = checkout.CreatedAt.UtcDateTime,
            ["lastSeenAtUtc"] = checkout.LastSeenAt.UtcDateTime,
            ["active"] = checkout.Active
        };
    }

    private static string RetainedSlotId(string projectId, SnapshotSlotKind kind, string key)
    {
        return $"slot_{CodeMeshHash.StableId(projectId, kind.ToString(), key)}";
    }

    private static CheckoutIdentityRecord CheckoutFromDocument(BsonDocument document)
    {
        return new CheckoutIdentityRecord(
            document["_id"].AsString,
            document["projectId"].AsString,
            document.GetValue("rootPath", "").AsString,
            DateTimeOffsetUtc(document["createdAtUtc"].ToUniversalTime()),
            DateTimeOffsetUtc(document["lastSeenAtUtc"].ToUniversalTime()),
            document.GetValue("active", true).ToBoolean());
    }

    private static BsonDocument SnapshotDocument(SnapshotIndexRecord snapshot)
    {
        return new BsonDocument
        {
            ["_id"] = snapshot.SnapshotId,
            ["projectId"] = snapshot.ProjectId,
            ["sourceViewHash"] = snapshot.SourceViewHash,
            ["ingestionScopeFingerprint"] = snapshot.IngestionScopeFingerprint,
            ["parserProfileFingerprint"] = snapshot.ParserProfileFingerprint,
            ["graphSchemaVersion"] = snapshot.GraphSchemaVersion,
            ["state"] = snapshot.State.ToString(),
            ["createdAtUtc"] = snapshot.CreatedAt.UtcDateTime,
            ["lastReferencedAtUtc"] = snapshot.LastReferencedAt.UtcDateTime,
            ["collectibleAfterUtc"] = OptionalDate(snapshot.CollectibleAfter),
            ["generationId"] = snapshot.GenerationId,
            ["nodeCount"] = snapshot.NodeCount,
            ["relationshipCount"] = snapshot.RelationshipCount,
            ["contentCount"] = snapshot.ContentCount,
            ["embeddingCount"] = snapshot.EmbeddingCount.HasValue ? snapshot.EmbeddingCount.Value : BsonNull.Value
        };
    }

    private static SnapshotIndexRecord SnapshotFromDocument(BsonDocument document)
    {
        return new SnapshotIndexRecord(
            document["_id"].AsString,
            document["projectId"].AsString,
            document.GetValue("sourceViewHash", "").AsString,
            document.GetValue("ingestionScopeFingerprint", "").AsString,
            document.GetValue("parserProfileFingerprint", "").AsString,
            document.GetValue("graphSchemaVersion", "").AsString,
            Enum.TryParse<SnapshotState>(document.GetValue("state", "Staging").AsString, out var state) ? state : SnapshotState.Staging,
            DateTimeOffsetUtc(document["createdAtUtc"].ToUniversalTime()),
            DateTimeOffsetUtc(document["lastReferencedAtUtc"].ToUniversalTime()),
            OptionalDate(document.GetValue("collectibleAfterUtc", BsonNull.Value)),
            document.GetValue("generationId", "").AsString,
            document.GetValue("nodeCount", 0).ToInt32(),
            document.GetValue("relationshipCount", 0).ToInt32(),
            document.GetValue("contentCount", 0).ToInt32(),
            OptionalInt(document.GetValue("embeddingCount", BsonNull.Value)));
    }

    private static BsonDocument SlotDocument(SnapshotSlotRecord slot)
    {
        return new BsonDocument
        {
            ["slotId"] = slot.SlotId,
            ["projectId"] = slot.ProjectId,
            ["kind"] = slot.Kind.ToString(),
            ["key"] = slot.Key,
            ["snapshotId"] = slot.SnapshotId,
            ["version"] = slot.Version,
            ["updatedAtUtc"] = slot.UpdatedAt.UtcDateTime,
            ["expiresAtUtc"] = OptionalDate(slot.ExpiresAt)
        };
    }

    private static IReadOnlyList<SnapshotSlotRecord> SlotsFromProjectDocument(BsonDocument? document)
    {
        if (document is null || !document.TryGetValue("slots", out var value) || !value.IsBsonArray)
        {
            return Array.Empty<SnapshotSlotRecord>();
        }

        return value.AsBsonArray
            .Where(item => item.IsBsonDocument)
            .Select(item =>
            {
                var slot = item.AsBsonDocument;
                return new SnapshotSlotRecord(
                    slot["slotId"].AsString,
                    slot["projectId"].AsString,
                    Enum.TryParse<SnapshotSlotKind>(slot["kind"].AsString, out var kind) ? kind : SnapshotSlotKind.CheckoutCurrent,
                    slot["key"].AsString,
                    slot["snapshotId"].AsString,
                    slot.GetValue("version", 0L).ToInt64(),
                    DateTimeOffsetUtc(slot["updatedAtUtc"].ToUniversalTime()),
                    OptionalDate(slot.GetValue("expiresAtUtc", BsonNull.Value)));
            })
            .ToArray();
    }

    private static BsonDocument GenerationDocument(IngestionGenerationRecord generation)
    {
        return new BsonDocument
        {
            ["_id"] = generation.GenerationId,
            ["projectId"] = generation.ProjectId,
            ["checkoutId"] = generation.CheckoutId,
            ["snapshotId"] = generation.SnapshotId,
            ["state"] = generation.State.ToString(),
            ["startedAtUtc"] = generation.StartedAt.UtcDateTime,
            ["finishedAtUtc"] = OptionalDate(generation.FinishedAt),
            ["error"] = generation.Error is null ? BsonNull.Value : generation.Error
        };
    }

    private static BsonDocument ObservationDocument(SnapshotObservationRecord observation)
    {
        return new BsonDocument
        {
            ["_id"] = observation.ObservationId,
            ["projectId"] = observation.ProjectId,
            ["checkoutId"] = observation.CheckoutId,
            ["snapshotId"] = observation.SnapshotId,
            ["branch"] = observation.Branch is null ? BsonNull.Value : observation.Branch,
            ["commit"] = observation.Commit is null ? BsonNull.Value : observation.Commit,
            ["workingTreeDirty"] = observation.WorkingTreeDirty,
            ["observedAtUtc"] = observation.ObservedAt.UtcDateTime,
            ["producerVersion"] = observation.ProducerVersion,
            ["ingestionRunId"] = observation.IngestionRunId
        };
    }

    private static BsonValue OptionalDate(DateTimeOffset? value)
    {
        return value.HasValue ? value.Value.UtcDateTime : BsonNull.Value;
    }

    private static DateTimeOffset? OptionalDate(BsonValue value)
    {
        return value.IsBsonNull ? null : DateTimeOffsetUtc(value.ToUniversalTime());
    }

    private static int? OptionalInt(BsonValue value)
    {
        return value.IsBsonNull ? null : value.ToInt32();
    }

    private static DateTimeOffset DateTimeOffsetUtc(DateTime value)
    {
        return new DateTimeOffset(DateTime.SpecifyKind(value, DateTimeKind.Utc));
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
        int SkippedEmbeddingCount,
        int SummaryCandidateCount = 0,
        int WrittenSummaryCount = 0,
        int SkippedSummaryCount = 0,
        int FailedSummaryCount = 0)
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
                stats.SkippedEmbeddingCount,
                stats.SummaryCandidateCount,
                stats.WrittenSummaryCount,
                stats.SkippedSummaryCount,
                stats.FailedSummaryCount);
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
                SkippedEmbeddingCount,
                SummaryCandidateCount,
                WrittenSummaryCount,
                SkippedSummaryCount,
                FailedSummaryCount);
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
