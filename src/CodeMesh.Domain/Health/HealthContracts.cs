namespace CodeMesh.Domain.Health;

public enum ComponentState
{
    Healthy,
    Degraded,
    Unhealthy,
    NotConfigured,
    Unknown
}

public sealed record ComponentHealth(
    string Name,
    ComponentState State,
    string Message,
    IReadOnlyDictionary<string, string> Metadata);

public sealed record HealthReport(
    string Service,
    ComponentState State,
    IReadOnlyList<ComponentHealth> Components,
    DateTimeOffset CheckedAt);
