# Third-party notices

CodeMesh-authored source and documentation are licensed under the repository's
[MIT License](LICENSE). This repository also refers to third-party packages,
container images, services, models, and evaluation repositories. Those
materials remain subject to their own terms.

The repository does not vendor or redistribute the container images or external
evaluation repositories listed below. Package and container tooling downloads
them separately when a user chooses the corresponding workflow.

## Runtime services referenced by Docker Compose

| Component | Referenced image | Upstream licence |
| --- | --- | --- |
| Neo4j Community Edition | `neo4j:5-community` | [GNU GPL v3](https://github.com/neo4j/neo4j/blob/2026.06/LICENSE.txt) |
| MongoDB Community Server | `mongo:7` | [Server Side Public License v1](https://www.mongodb.com/legal/licensing/community-edition) |
| Qdrant | `qdrant/qdrant:latest` | [Apache License 2.0](https://github.com/qdrant/qdrant/blob/master/LICENSE) |
| Ollama | `ollama/ollama:latest` | [MIT License](https://github.com/ollama/ollama/blob/main/LICENSE) |

MongoDB states that the SSPL service condition applies when MongoDB's
functionality is offered to third parties as a service, and not to another SaaS
application merely using MongoDB as its database. Review the
[MongoDB SSPL FAQ](https://www.mongodb.com/legal/licensing/server-side-public-license/faq)
for the intended deployment model.

## Build and application dependencies

- The Agent Access image derives from `python:3.14-slim`. Python is available
  under the [Python Software Foundation License](https://docs.python.org/3/license.html),
  and the image contains separately licensed operating-system components.
- The C# parser images derive from the official .NET SDK and ASP.NET 10 images.
  Microsoft publishes [container licence information](https://aka.ms/mcr/osslegalnotice)
  and [Linux image component guidance](https://github.com/dotnet/dotnet-docker/blob/main/documentation/image-artifact-details.md).
- `agent-access/uv.lock` and the NuGet `packages.lock.json` files identify
  application dependencies. They do not replace the licence and notice files
  supplied with those packages.

## Models and evaluation repositories

CodeMesh does not bundle model weights. A user who enables a model provider is
responsible for the selected model's licence and acceptable-use terms. The
external YoutubeDownloader evaluation repository is not vendored; its pinned
source remains under its upstream MIT licence.

## Distribution boundary

Publishing this source repository does not itself redistribute the referenced
container images, model weights, or external repositories. Before distributing
a built image, binary, installer, appliance, or hosted database service, inspect
the exact artifact contents and preserve every licence, notice, source-offer, or
service obligation that applies to that distribution.
