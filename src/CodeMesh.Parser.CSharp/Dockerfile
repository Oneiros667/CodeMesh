FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY CodeMesh.sln ./
COPY src/CodeMesh.Domain/ ./src/CodeMesh.Domain/
COPY src/CodeMesh.Parser.CSharp/ ./src/CodeMesh.Parser.CSharp/

RUN dotnet restore src/CodeMesh.Parser.CSharp/CodeMesh.Parser.CSharp.csproj
RUN dotnet publish src/CodeMesh.Parser.CSharp/CodeMesh.Parser.CSharp.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app/publish ./

ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "CodeMesh.Parser.CSharp.dll"]
