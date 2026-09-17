# Decision: Isolate parser container design-time outputs

- Status: implemented locally
- Date: 2026-09-05
- Owners: CodeMesh maintainers

## Context

The SDK runtime added in [decision 0004](0004-parser-container-requires-dotnet-sdk.md)
loads projects, but MSBuild attempts to write generated editor configuration and
assembly-info caches into a read-only repository. Suppressing generation would
remove compiler-visible metadata and could change the compilation context.

## Decision

The parser container installs `CodeMesh.DesignTime.targets` as an additive SDK
`Microsoft.Common.targets/ImportBefore` extension. It acts only for design-time
builds carrying the parser's private `CodeMeshDesignTimeOutputRoot` property.
Each workspace receives a request-owned temporary directory. A SHA-256 key of
project path, configuration, platform, target framework, and runtime identifier
separates projects and evaluation variants within that directory.

The extension redirects standard intermediate and build output directories
before common targets calculate generated file paths. It preserves generation,
compiler-visible values, project references, and the original project extension
directory used to read existing NuGet assets. It does not disable generators,
replace repository imports, or change source paths. The output scope outlives
workspace loading and compilation creation and is deleted after workspace
disposal, including project failure paths.

This is a parser-container integration. Host SDK installations are not modified.
The target file is packaged with the parser; deterministic tests import it into
explicit fixtures. The C# extractor capability advances to `0.2.3`, independently
of application version `0.1.0`, so fresh ingestion can identify the changed
project-loading behavior. Existing indexed snapshots are not silently rebound.

## Consequences

- Standard SDK design-time output can be generated while the repository mount
  remains read-only.
- Concurrent requests and same-named projects have isolated output paths.
- NuGet assets and source continue to resolve from their original locations.
- Custom project targets with independent write paths can still fail on a
  read-only mount. The extension is not a sandbox for untrusted MSBuild code,
  an implicit restore, or a guarantee for every SDK/project configuration.
- Abrupt process termination can leave temporary files until the disposable
  container is removed; normal completion and observed failure paths clean up.

## Verification

The deterministic suite checks compiler-visible metadata, same-named concurrent
projects, deliberate failure cleanup, and cross-project invocation edges with
the extension active. All 71 .NET tests pass with no skips; 228 Python tests and
five MCP fixture cases pass. The parser container builds and loads
CodeMesh.Domain through a verified read-only mount twice concurrently, with
1,229 nodes, 1,906 relationships, no warning/error diagnostics, and zero
remaining request directories. The two results are identical after excluding
only content observation timestamps.

The implementation follows the SDK's additive import hooks and supported
[MSBuild SHA-256 property function](https://learn.microsoft.com/en-us/visualstudio/msbuild/property-functions#msbuild-stablestringhash).
The earlier warning and intermediate editor-config-only failure remain
historical diagnostics; the current probe covers standard design-time outputs.

Revisit this extension when an SDK supplies an equivalent native read-only
workspace mode. Expand it only for a reproduced design-time output failure with
metadata and relationship parity checks; remove it if the supported SDK no
longer needs the redirection.
