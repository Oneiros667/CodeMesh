namespace CodeMesh.Domain.Contracts;

public enum SnapshotState
{
    Staging,
    Active,
    Collectible,
    Failed
}

public enum SnapshotSlotKind
{
    BranchHead,
    CheckoutCurrent,
    ExplicitPin,
    Evidence
}

public enum IngestionGenerationState
{
    Staging,
    Published,
    Failed
}

public sealed record ProjectIdentityRecord(
    string ProjectId,
    string Alias,
    string? RemoteUrl,
    DateTimeOffset CreatedAt,
    DateTimeOffset LastSeenAt);

public sealed record CheckoutIdentityRecord(
    string CheckoutId,
    string ProjectId,
    string RootPath,
    DateTimeOffset CreatedAt,
    DateTimeOffset LastSeenAt,
    bool Active = true);

public sealed record SnapshotIndexRecord(
    string SnapshotId,
    string ProjectId,
    string SourceViewHash,
    string IngestionScopeFingerprint,
    string ParserProfileFingerprint,
    string GraphSchemaVersion,
    SnapshotState State,
    DateTimeOffset CreatedAt,
    DateTimeOffset LastReferencedAt,
    DateTimeOffset? CollectibleAfter,
    string GenerationId,
    int NodeCount,
    int RelationshipCount,
    int ContentCount,
    int? EmbeddingCount);

public sealed record SnapshotSlotRecord(
    string SlotId,
    string ProjectId,
    SnapshotSlotKind Kind,
    string Key,
    string SnapshotId,
    long Version,
    DateTimeOffset UpdatedAt,
    DateTimeOffset? ExpiresAt = null);

public sealed record SnapshotObservationRecord(
    string ObservationId,
    string ProjectId,
    string CheckoutId,
    string SnapshotId,
    string? Branch,
    string? Commit,
    bool WorkingTreeDirty,
    DateTimeOffset ObservedAt,
    string ProducerVersion,
    string IngestionRunId);

public sealed record IngestionGenerationRecord(
    string GenerationId,
    string ProjectId,
    string CheckoutId,
    string SnapshotId,
    IngestionGenerationState State,
    DateTimeOffset StartedAt,
    DateTimeOffset? FinishedAt,
    string? Error);

public sealed record SnapshotSlotExpectation(string SlotId, string? SnapshotId, long? Version);

public sealed record SnapshotPublication(
    ProjectIdentityRecord Project,
    CheckoutIdentityRecord Checkout,
    SnapshotIndexRecord Snapshot,
    SnapshotObservationRecord Observation,
    IngestionGenerationRecord Generation,
    IReadOnlyList<SnapshotSlotRecord> Slots,
    IReadOnlyList<SnapshotSlotExpectation> ExpectedSlots,
    TimeSpan UnreferencedGracePeriod);

public sealed record SnapshotPublicationResult(
    bool Published,
    IReadOnlyList<SnapshotSlotRecord> Slots,
    IReadOnlyList<string> NewlyCollectibleSnapshotIds,
    string? Conflict);

public sealed record SnapshotSlotMutationResult(
    bool Changed,
    SnapshotSlotRecord? Slot,
    IReadOnlyList<string> NewlyCollectibleSnapshotIds,
    string? Conflict);
