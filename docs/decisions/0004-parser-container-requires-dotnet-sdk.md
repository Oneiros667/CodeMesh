# Decision: Include the .NET SDK in the C# parser runtime

- Status: implemented locally
- Date: 2026-09-05
- Owners: CodeMesh maintainers

## Context

The parser's container used the ASP.NET runtime image. Its service started and
reported healthy, but a project parse through `MSBuildWorkspace` reported
`CMSHARP012` because no .NET SDK was installed, followed by `CMSHARP010`
filesystem fallback. A healthy HTTP endpoint therefore did not establish the
container's advertised project/solution parsing capability.

## Decision

Use the .NET 10 SDK image for the final parser container as well as its build
stage. Keep the existing read-only repository mount and loopback service
binding. Include the canonical version props and file in the restricted Docker
build context. Use an explicit `PublishDir` property for the publish output.

The application source version and `ParserCapability.Version` serve different
purposes. The parser capability version identifies extractor behavior and is
not replaced by the application release version.

## Consequences

- Roslyn project loading has the SDK and MSBuild tooling it requires.
- The runtime image is larger and includes build tools; release evidence must
  retain the exact image digest and dependency assessment.
- Referenced projects and assets still need compatible SDKs and dependencies.
  This change does not guarantee that every repository loads or authorize
  network restores, arbitrary build execution, or broader repository access.
- Health checks remain service-liveness evidence. Acceptance must exercise
  parsing and inspect diagnostics for project-loading failure and fallback.

## Verification

Build the parser image, start it in the disposable Compose project, and request
`/parse` for the mounted CodeMesh.Domain project. Require nonempty nodes and
relationships, no error diagnostics, and neither `CMSHARP012` nor `CMSHARP010`.
Retain the initial runtime-only failure and the corrected image's result in the
local package verification evidence. Both application suites and the full
provider-free end-to-end smoke remain part of the surrounding validation.

The corrected probe loaded CodeMesh.Domain with 1,229 nodes and 1,906
relationships. It retained a `CMSHARP015` warning for generated editor-config
output on the read-only mount and an informational `CMSHARP011` project-loaded
diagnostic. No project-loading failure, filesystem fallback, or error
was reported. The warning remains an environment-acceptance limitation.
