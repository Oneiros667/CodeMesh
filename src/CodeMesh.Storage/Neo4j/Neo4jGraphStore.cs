using System.Text.Json;
using CodeMesh.Domain.Graph;
using CodeMesh.Domain.Health;
using Neo4j.Driver;

namespace CodeMesh.Storage.Neo4j;

public sealed record Neo4jGraphStoreOptions(
    string Uri,
    string User,
    string Password,
    string? Database = null);

public sealed class Neo4jGraphStore : IGraphStore, IStoreHealthCheck, IAsyncDisposable
{
    private readonly IDriver _driver;
    private readonly string _uri;
    private readonly string? _database;
    private readonly SemaphoreSlim _schemaLock = new(1, 1);
    private bool _schemaReady;

    public Neo4jGraphStore(Neo4jGraphStoreOptions options)
        : this(
            GraphDatabase.Driver(options.Uri, AuthTokens.Basic(options.User, options.Password)),
            options.Database,
            options.Uri)
    {
    }

    public Neo4jGraphStore(IDriver driver, string? database = null, string uri = "neo4j")
    {
        _driver = driver;
        _uri = uri;
        _database = string.IsNullOrWhiteSpace(database) ? null : database;
        Name = _database is null ? "neo4j" : $"neo4j:{_database}";
    }

    public string Name { get; }

    public async Task UpsertGraphAsync(CodeGraphBatch batch, CancellationToken cancellationToken = default)
    {
        await EnsureSchemaAsync(cancellationToken).ConfigureAwait(false);

        await using var session = OpenSession();

        if (batch.Nodes.Count > 0)
        {
            await RunAndConsumeAsync(
                session,
                """
                UNWIND $nodes AS node
                MERGE (n:CodeMeshNode {id: node.id})
                SET n += node
                """,
                new { nodes = batch.Nodes.Select(ToNodeProperties).ToArray() },
                cancellationToken).ConfigureAwait(false);
        }

        if (batch.Relationships.Count > 0)
        {
            await RunAndConsumeAsync(
                session,
                """
                UNWIND $relationships AS relationship
                MATCH (source:CodeMeshNode {id: relationship.sourceNodeId})
                MATCH (target:CodeMeshNode {id: relationship.targetNodeId})
                MERGE (source)-[r:CODEMESH_REL {id: relationship.id}]->(target)
                SET r += relationship
                """,
                new { relationships = batch.Relationships.Select(ToRelationshipProperties).ToArray() },
                cancellationToken).ConfigureAwait(false);
        }
    }

    public async Task<CodeNode?> GetNodeAsync(string nodeId, CancellationToken cancellationToken = default)
    {
        await using var session = OpenSession();
        var cursor = await session.RunAsync(
            "MATCH (n:CodeMeshNode {id: $nodeId}) RETURN n LIMIT 1",
            new { nodeId }).ConfigureAwait(false);
        var record = await cursor.SingleOrDefaultAsync().ConfigureAwait(false);

        return record is null ? null : ToCodeNode(record["n"].As<INode>());
    }

    public async Task<IReadOnlyList<CodeRelationship>> GetRelationshipsAsync(
        string nodeId,
        int depth = 1,
        CancellationToken cancellationToken = default)
    {
        await using var session = OpenSession();
        var cursor = await session.RunAsync(
            """
            MATCH (:CodeMeshNode {id: $nodeId})-[r:CODEMESH_REL]-(:CodeMeshNode)
            RETURN r
            ORDER BY r.id
            """,
            new { nodeId }).ConfigureAwait(false);
        var records = await cursor.ToListAsync().ConfigureAwait(false);

        return records
            .Select(record => ToCodeRelationship(record["r"].As<IRelationship>()))
            .ToArray();
    }

    public async Task<ComponentHealth> CheckAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            await _driver.VerifyConnectivityAsync().ConfigureAwait(false);

            return new ComponentHealth(
                Name,
                ComponentState.Healthy,
                "Neo4j graph store is available.",
                Metadata());
        }
        catch (Exception exception) when (exception is Neo4jException or ServiceUnavailableException)
        {
            var metadata = Metadata();
            metadata["detail"] = exception.Message;

            return new ComponentHealth(
                Name,
                ComponentState.Degraded,
                "Neo4j graph store is not reachable.",
                metadata);
        }
    }

    public async ValueTask DisposeAsync()
    {
        _schemaLock.Dispose();
        await _driver.DisposeAsync().ConfigureAwait(false);
    }

    private async Task EnsureSchemaAsync(CancellationToken cancellationToken)
    {
        if (_schemaReady)
        {
            return;
        }

        await _schemaLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_schemaReady)
            {
                return;
            }

            await using var session = OpenSession();
            await RunAndConsumeAsync(
                session,
                "CREATE CONSTRAINT codemesh_node_id IF NOT EXISTS FOR (n:CodeMeshNode) REQUIRE n.id IS UNIQUE",
                new { },
                cancellationToken).ConfigureAwait(false);
            await RunAndConsumeAsync(
                session,
                "CREATE INDEX codemesh_relationship_id IF NOT EXISTS FOR ()-[r:CODEMESH_REL]-() ON (r.id)",
                new { },
                cancellationToken).ConfigureAwait(false);

            _schemaReady = true;
        }
        finally
        {
            _schemaLock.Release();
        }
    }

    private IAsyncSession OpenSession()
    {
        return _database is null
            ? _driver.AsyncSession()
            : _driver.AsyncSession(builder => builder.WithDatabase(_database));
    }

    private static async Task RunAndConsumeAsync(
        IAsyncQueryRunner runner,
        string query,
        object parameters,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();

        var cursor = await runner.RunAsync(query, parameters).ConfigureAwait(false);
        await cursor.ConsumeAsync().ConfigureAwait(false);
    }

    private Dictionary<string, string> Metadata()
    {
        var metadata = new Dictionary<string, string>
        {
            ["uri"] = _uri
        };

        if (_database is not null)
        {
            metadata["database"] = _database;
        }

        return metadata;
    }

    private static Dictionary<string, object?> ToNodeProperties(CodeNode node)
    {
        return new Dictionary<string, object?>
        {
            ["id"] = node.Id,
            ["stableKey"] = node.StableKey,
            ["kind"] = node.Kind.ToString(),
            ["name"] = node.Name,
            ["language"] = node.Language,
            ["project"] = node.Project,
            ["contentHash"] = node.ContentHash,
            ["filePath"] = node.Span.FilePath,
            ["startLine"] = node.Span.StartLine,
            ["startColumn"] = node.Span.StartColumn,
            ["endLine"] = node.Span.EndLine,
            ["endColumn"] = node.Span.EndColumn,
            ["metadataJson"] = JsonSerializer.Serialize(node.Metadata)
        };
    }

    private static Dictionary<string, object?> ToRelationshipProperties(CodeRelationship relationship)
    {
        return new Dictionary<string, object?>
        {
            ["id"] = relationship.Id,
            ["sourceNodeId"] = relationship.SourceNodeId,
            ["targetNodeId"] = relationship.TargetNodeId,
            ["kind"] = relationship.Kind.ToString(),
            ["label"] = relationship.Label,
            ["metadataJson"] = JsonSerializer.Serialize(relationship.Metadata)
        };
    }

    private static CodeNode ToCodeNode(INode node)
    {
        return new CodeNode(
            RequiredString(node, "id"),
            RequiredString(node, "stableKey"),
            ParseEnum<CodeNodeKind>(RequiredString(node, "kind")),
            RequiredString(node, "name"),
            RequiredString(node, "language"),
            RequiredString(node, "project"),
            new SourceSpan(
                RequiredString(node, "filePath"),
                RequiredInt(node, "startLine"),
                RequiredInt(node, "startColumn"),
                RequiredInt(node, "endLine"),
                RequiredInt(node, "endColumn")),
            RequiredString(node, "contentHash"),
            ParseMetadata(RequiredString(node, "metadataJson")));
    }

    private static CodeRelationship ToCodeRelationship(IRelationship relationship)
    {
        return new CodeRelationship(
            RequiredString(relationship, "id"),
            RequiredString(relationship, "sourceNodeId"),
            RequiredString(relationship, "targetNodeId"),
            ParseEnum<CodeRelationshipKind>(RequiredString(relationship, "kind")),
            OptionalString(relationship, "label"),
            ParseMetadata(RequiredString(relationship, "metadataJson")));
    }

    private static string RequiredString(IEntity entity, string key)
    {
        return entity.Properties.TryGetValue(key, out var value) && value is not null
            ? value.ToString() ?? string.Empty
            : string.Empty;
    }

    private static string? OptionalString(IEntity entity, string key)
    {
        return entity.Properties.TryGetValue(key, out var value) && value is not null
            ? value.ToString()
            : null;
    }

    private static int RequiredInt(IEntity entity, string key)
    {
        if (!entity.Properties.TryGetValue(key, out var value) || value is null)
        {
            return 0;
        }

        return value switch
        {
            int number => number,
            long number => checked((int)number),
            _ => int.TryParse(value.ToString(), out var number) ? number : 0
        };
    }

    private static TEnum ParseEnum<TEnum>(string value)
        where TEnum : struct
    {
        return Enum.TryParse<TEnum>(value, ignoreCase: true, out var parsed)
            ? parsed
            : default;
    }

    private static IReadOnlyDictionary<string, string> ParseMetadata(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return new Dictionary<string, string>();
        }

        return JsonSerializer.Deserialize<Dictionary<string, string>>(json)
            ?? new Dictionary<string, string>();
    }
}
