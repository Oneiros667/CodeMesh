# CodeMesh SDLC Roadmap

CodeMesh currently focuses on code intelligence: parsing implementation code, writing graph/content/vector/summary data, and exposing that context to coding agents through REST, MCP, CLI, and .NET client surfaces.

Future work can extend CodeMesh into a broader software development lifecycle intelligence layer. The goal is not to index every file as undifferentiated text, but to parse high-value SDLC artifacts into typed nodes, relationships, raw content, and agent-ready context packages.

## Guiding Principle

CodeMesh should help agents answer questions about intent, compatibility, validation, deployment, ownership, and production behavior, not only questions about classes and methods.

Structured artifact formats should receive schema-aware parsers where practical. Unknown or uncommon formats can still be indexed lexically as raw content, but first-class graph value comes from typed nodes and relationships.

## Priority Areas

### 1. Runtime And Deployment Context

Deployment artifacts connect source code to running systems.

Candidate inputs:

- `Dockerfile` and container build files. Initial parser support exists for Dockerfile stages and selected stage metadata.
- `docker-compose.yml` and compose overrides. Initial parser support exists for Compose services and selected service metadata.
- Helm charts and Kubernetes manifests.
- Deployment environment overlays and values files.
- CI/CD deployment jobs where they directly build or release services.

Candidate nodes:

- `ContainerImage`
- `DockerfileStage`
- `ComposeService`
- `HelmChart`
- `KubernetesDeployment`
- `KubernetesService`
- `Ingress`
- `ConfigValue`
- `SecretReference`
- `Pipeline`
- `PipelineJob`

Candidate relationships:

- `BuildsImage`
- `RunsService`
- `DeploysTo`
- `DependsOn`
- `ExposesPort`
- `UsesEnvVar`
- `MountsVolume`
- `ReferencesProject`
- `RunsCommand`

Useful agent questions:

- Which deployment files reference this service, port, image, or environment variable?
- What runtime configuration must change with this code change?
- Which Kubernetes resources run this component?
- What local compose services are required to reproduce this behavior?

Current implementation:

- `src/CodeMesh.Parser.Deployment` parses Dockerfiles and common Compose file names.
- It emits `Dockerfile`, `DockerfileStage`, `ComposeFile`, and `ComposeService` nodes.
- It captures base images, build contexts, Dockerfile references, ports, environment keys, volumes, and Compose `depends_on` relationships.
- Helm, Kubernetes, CI/CD workflows, environment overlays, secret references, image build lineage, and code-to-runtime links remain future work.

### 2. API And Integration Contracts

Contracts often define compatibility boundaries more directly than implementation code.

Candidate inputs:

- OpenAPI/Swagger documents.
- AsyncAPI documents.
- GraphQL schemas.
- Protobuf and gRPC contracts.
- Message schemas and event contracts.

Useful agent questions:

- Which public endpoints or messages are affected by this change?
- Is this API change backward compatible?
- Which clients, handlers, or generated code reference this contract?

### 3. Database And Persistence Lifecycle

Persistence artifacts define rollout risk and data compatibility.

Candidate inputs:

- SQL migration files.
- ORM migration metadata.
- Database schema snapshots.
- Seed data.
- Index definitions.
- Backup, restore, and maintenance scripts.

Useful agent questions:

- Which migrations are required for this model change?
- Does a code path depend on a column, table, index, or document shape?
- Is this change safe to roll forward and roll back?

### 4. Tests And Quality Signals

Validation context helps agents choose the right checks before and after edits.

Candidate inputs:

- Unit, integration, and end-to-end test metadata.
- Coverage reports.
- Test run history.
- Flaky test records.
- Static analysis, lint, and formatting results.
- Mutation testing reports.

Useful agent questions:

- Which tests validate this code path?
- What coverage exists for this component?
- Which quality checks are expected before merging?

### 5. Requirements, Product Intent, And Architecture

Intent artifacts help agents preserve behavior and avoid local-only fixes.

Candidate inputs:

- Issues, epics, and user stories.
- ADRs.
- Design documents.
- Architecture diagrams or structured architecture metadata.
- Product specs.
- README and developer documentation.
- Release notes and changelogs.

Useful agent questions:

- What requirement or decision explains this code?
- Is this change consistent with the intended architecture?
- Which documented behavior must remain stable?

### 6. Observability And Operations

Operational context connects code to production diagnosis.

Candidate inputs:

- Logging conventions.
- Metrics definitions.
- Dashboard definitions.
- Alert rules.
- Runbooks.
- SLOs and SLIs.
- Incident notes.

Useful agent questions:

- How would production show that this path is failing?
- Which alerts or dashboards cover this service?
- What runbook applies to this failure mode?

### 7. Security, Compliance, And Supply Chain

Security context is high value but should be handled with deliberate sensitivity.

Candidate inputs:

- Threat models.
- Authorization policies.
- Role and permission definitions.
- SAST and DAST results.
- Dependency vulnerability reports.
- SBOMs.
- Secret references, not secret values.

Useful agent questions:

- Which permissions or policies gate this code path?
- Does this dependency or container image have known risk?
- Which security checks should run for this change?

### 8. Ownership And Collaboration Metadata

Ownership context helps agents understand review and maintenance boundaries.

Candidate inputs:

- `CODEOWNERS`.
- Team ownership maps.
- PR templates.
- Contribution guides.
- Review history metadata.

Useful agent questions:

- Who owns this component?
- What review expectations apply to this area?
- Which conventions should an agent follow before proposing a change?

## Suggested Implementation Sequence

1. Add runtime/deployment ingestion for Dockerfile, Docker Compose, and Helm.
2. Add API contract and database migration ingestion.
3. Add test, coverage, and quality report ingestion.
4. Add ADR, architecture, and requirements indexing.
5. Add observability and runbook indexing.
6. Add security and supply-chain metadata with careful redaction rules.
7. Add ownership and review metadata.

Each phase should expose its artifacts through the same Agent Access model already used for code: context search, context packages, symbols or named-resource lookup where appropriate, graph neighbors, and MCP tools.
