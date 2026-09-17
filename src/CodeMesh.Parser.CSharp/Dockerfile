FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY CodeMesh.sln ./
COPY NuGet.config ./
COPY Directory.Build.props VERSION ./
COPY src/CodeMesh.Domain/ ./src/CodeMesh.Domain/
COPY src/CodeMesh.Parser.CSharp/ ./src/CodeMesh.Parser.CSharp/

RUN dotnet restore src/CodeMesh.Parser.CSharp/CodeMesh.Parser.CSharp.csproj --locked-mode
RUN dotnet publish src/CodeMesh.Parser.CSharp/CodeMesh.Parser.CSharp.csproj -c Release -p:PublishDir=/app/publish/ --no-restore

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS runtime
WORKDIR /app
COPY --from=build /app/publish ./

RUN codemesh_sdk_version="$(dotnet --version)" \
    && codemesh_import_dir="/usr/share/dotnet/sdk/$codemesh_sdk_version/Current/Microsoft.Common.targets/ImportBefore" \
    && mkdir -p "$codemesh_import_dir" \
    && cp /app/CodeMesh.DesignTime.targets "$codemesh_import_dir/CodeMesh.DesignTime.targets"

ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "CodeMesh.Parser.CSharp.dll"]
