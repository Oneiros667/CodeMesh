param(
    [string]$RepositoryRoot,
    [string]$SolutionPath,
    [string]$AgentAccessUrl = "http://127.0.0.1:8088",
    [switch]$IncludeEmbeddings,
    [switch]$ForceEmbeddings,
    [string]$EmbeddingProvider = $env:CODEMESH_MODEL_PROVIDER,
    [string]$EmbeddingModel = $env:CODEMESH_EMBEDDING_MODEL,
    [string]$OllamaUrl = $env:CODEMESH_OLLAMA_URL,
    [string]$LmStudioUrl = $env:CODEMESH_LM_STUDIO_URL,
    [switch]$SkipCompose,
    [switch]$UseConfiguredSample,
    [switch]$KeepFixture
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$fixtureRoot = Join-Path $repoRoot ".codemesh-smoke\Fixture"
$projectPath = Join-Path $fixtureRoot "CodeMeshSmokeFixture.csproj"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message"
}

function Wait-Http {
    param(
        [string]$Url,
        [int]$Attempts = 40,
        [int]$DelaySeconds = 3
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5 | Out-Null
            return
        }
        catch {
            if ($attempt -eq $Attempts) {
                throw "Timed out waiting for $Url. Last error: $($_.Exception.Message)"
            }

            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

function New-SmokeFixture {
    $fixtureParent = Split-Path $fixtureRoot -Parent
    $resolvedParent = [System.IO.Path]::GetFullPath($fixtureParent)
    $resolvedRepo = [System.IO.Path]::GetFullPath($repoRoot)
    if (!$resolvedParent.StartsWith($resolvedRepo, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to write smoke fixture outside repository root: $resolvedParent"
    }

    if (Test-Path $fixtureRoot) {
        Remove-Item -LiteralPath $fixtureRoot -Recurse -Force
    }

    New-Item -ItemType Directory -Path $fixtureRoot | Out-Null

    @"
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>
"@ | Set-Content -LiteralPath $projectPath -Encoding UTF8

    @"
namespace CodeMeshSmoke;

public sealed class Downloader
{
    private string _lastUrl = "";

    public string LastUrl
    {
        get => _lastUrl;
        private set => _lastUrl = value;
    }

    public Task<string> DownloadAsync(string url)
    {
        LastUrl = Normalize(url);
        return Task.FromResult($"download:{LastUrl}");
    }

    private static string Normalize(string url)
    {
        return url.Trim().ToLowerInvariant();
    }
}
"@ | Set-Content -LiteralPath (Join-Path $fixtureRoot "Downloader.cs") -Encoding UTF8
}

function Invoke-JsonCommand {
    param([string[]]$Arguments)

    $output = & dotnet @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: dotnet $($Arguments -join ' ')`n$output"
    }

    return ($output | Out-String | ConvertFrom-Json)
}

function Normalize-Provider {
    param([string]$Provider)

    $value = "$Provider".Trim().ToLowerInvariant()
    if ($value -in @("lm-studio", "lm_studio")) {
        return "lmstudio"
    }

    return $value
}

if ($UseConfiguredSample) {
    if (![string]::IsNullOrWhiteSpace($RepositoryRoot) -or ![string]::IsNullOrWhiteSpace($SolutionPath)) {
        throw "Use either -UseConfiguredSample or explicit -RepositoryRoot/-SolutionPath, not both."
    }

    $RepositoryRoot = $env:CODEMESH_SAMPLE_CSHARP_ROOT
    $SolutionPath = $env:CODEMESH_SAMPLE_CSHARP_SOLUTION
    if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
        throw "CODEMESH_SAMPLE_CSHARP_ROOT is required when -UseConfiguredSample is set."
    }

    if ([string]::IsNullOrWhiteSpace($SolutionPath)) {
        $SolutionPath = $RepositoryRoot
    }
}
elseif ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    New-SmokeFixture
    $RepositoryRoot = $fixtureRoot
    $SolutionPath = $projectPath
}
elseif ([string]::IsNullOrWhiteSpace($SolutionPath)) {
    $SolutionPath = $RepositoryRoot
}

if (!(Test-Path -LiteralPath $RepositoryRoot)) {
    throw "Repository root not found: $RepositoryRoot"
}

if (!(Test-Path -LiteralPath $SolutionPath)) {
    throw "Solution/project path not found: $SolutionPath"
}

if ([string]::IsNullOrWhiteSpace($EmbeddingProvider) -or $EmbeddingProvider -eq "none") {
    $EmbeddingProvider = "ollama"
}

if ([string]::IsNullOrWhiteSpace($EmbeddingModel)) {
    $EmbeddingModel = if ($EmbeddingProvider -in @("lmstudio", "lm-studio", "lm_studio")) {
        "text-embedding-nomic-embed-text-v1.5"
    }
    else {
        "nomic-embed-text:latest"
    }
}

if (!$SkipCompose) {
    Write-Step "Starting CodeMesh stores and Agent Access"
    & docker compose up -d --build neo4j mongodb qdrant agent-access
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed."
    }
}

Write-Step "Waiting for Agent Access"
Wait-Http "$AgentAccessUrl/health"

Write-Step "Ingesting smoke repository"
$ingestArgs = @(
    "run",
    "--project",
    "src/CodeMesh.Cli",
    "--",
    "ingest",
    "--root",
    $RepositoryRoot,
    "--project",
    $SolutionPath,
    "--json"
)

if ($IncludeEmbeddings) {
    $ingestArgs += @(
        "--include-embeddings",
        "--embedding-provider",
        $EmbeddingProvider,
        "--embedding-model",
        $EmbeddingModel
    )

    if ($ForceEmbeddings) {
        $ingestArgs += "--force-embeddings"
    }

    if ($EmbeddingProvider -eq "ollama" -and ![string]::IsNullOrWhiteSpace($OllamaUrl)) {
        $ingestArgs += @("--ollama-url", $OllamaUrl)
    }
    elseif ($EmbeddingProvider -in @("lmstudio", "lm-studio", "lm_studio") -and ![string]::IsNullOrWhiteSpace($LmStudioUrl)) {
        $ingestArgs += @("--lm-studio-url", $LmStudioUrl)
    }
}
else {
    $ingestArgs += "--skip-embeddings"
}

$ingest = Invoke-JsonCommand $ingestArgs
$repositoryId = $ingest.Repository.Id
if ([string]::IsNullOrWhiteSpace($repositoryId)) {
    throw "Ingestion did not return a repository id."
}

Write-Host "Repository: $repositoryId"
Write-Host "Nodes: $($ingest.NodeCount), relationships: $($ingest.RelationshipCount), content: $($ingest.ContentCount), embeddings: $($ingest.EmbeddingCount)"

if ($IncludeEmbeddings) {
    Write-Step "Verifying embeddings"
    $verifyArgs = @(
        "run",
        "--project",
        "src/CodeMesh.Cli",
        "--",
        "embeddings",
        "verify",
        $repositoryId,
        "--embedding-provider",
        $EmbeddingProvider,
        "--embedding-model",
        $EmbeddingModel,
        "--json"
    )
    $verify = Invoke-JsonCommand $verifyArgs
    if (!$verify.IsComplete) {
        throw "Embedding verification failed: $($verify | ConvertTo-Json -Depth 8)"
    }

    Write-Host "Embeddings verified: $($verify.CurrentEmbeddingCount) current vector(s)."
}

Write-Step "Checking repository registry through Agent Access"
$repositories = Invoke-RestMethod -Uri "$AgentAccessUrl/repositories" -Method Get -TimeoutSec 15
$registered = @($repositories.repositories) | Where-Object { $_.repository_id -eq $repositoryId } | Select-Object -First 1
if ($null -eq $registered) {
    throw "Agent Access did not list ingested repository $repositoryId."
}
Write-Host "Registry alias: $($registered.alias)"

Write-Step "Running context search"
$searchBody = @{
    query = "DownloadAsync"
    repository_id = $repositoryId
    limit = 5
    kinds = @("Method", "Class")
    filters = @{}
} | ConvertTo-Json -Depth 8
$search = Invoke-RestMethod -Uri "$AgentAccessUrl/context/search" -Method Post -ContentType "application/json" -Body $searchBody -TimeoutSec 30
if (@($search.hits).Count -eq 0) {
    throw "Context search returned no hits."
}
if ($null -eq $search.diagnostics) {
    throw "Context search response did not include diagnostics metadata."
}

$searchHitCount = @($search.hits).Count
$searchDiagnostics = $search.diagnostics
if ($searchDiagnostics.mode -notin @("vector", "lexical", "hybrid")) {
    throw "Context search diagnostics returned unexpected mode: $($searchDiagnostics.mode)"
}
if ([int]$searchDiagnostics.hit_count -ne $searchHitCount) {
    throw "Context search diagnostics hit_count $($searchDiagnostics.hit_count) did not match returned hit count $searchHitCount."
}
if ([int]$searchDiagnostics.vector_hit_count -lt 0) {
    throw "Context search diagnostics vector_hit_count cannot be negative: $($searchDiagnostics.vector_hit_count)"
}
if ([int]$searchDiagnostics.lexical_hit_count -lt 0) {
    throw "Context search diagnostics lexical_hit_count cannot be negative: $($searchDiagnostics.lexical_hit_count)"
}
if ($searchDiagnostics.mode -in @("vector", "hybrid") -and !$searchDiagnostics.vector_available) {
    throw "Context search diagnostics reported vector-backed mode without vector_available=true."
}
if ($searchDiagnostics.mode -in @("vector", "hybrid") -and $searchDiagnostics.lexical_fallback) {
    throw "Context search diagnostics reported vector-backed mode with lexical_fallback=true."
}
if ($searchDiagnostics.lexical_fallback -and $searchDiagnostics.vector_available -and [int]$searchDiagnostics.vector_hit_count -ne 0) {
    throw "Context search diagnostics reported lexical fallback with vector hits."
}

$agentProvider = Normalize-Provider $searchDiagnostics.model_provider
$expectedProvider = Normalize-Provider $EmbeddingProvider
if ($IncludeEmbeddings -and $agentProvider -eq $expectedProvider -and $agentProvider -in @("ollama", "lmstudio")) {
    if (!$searchDiagnostics.embedding_attempted) {
        throw "Context search diagnostics did not report an embedding attempt for configured Agent Access provider '$agentProvider'."
    }
    if (!$searchDiagnostics.vector_available) {
        throw "Context search diagnostics did not report a query vector for configured Agent Access provider '$agentProvider'."
    }
    if ([int]$searchDiagnostics.vector_hit_count -eq 0) {
        throw "Context search diagnostics did not report vector hits for embedding provider '$agentProvider'."
    }
    if ($searchDiagnostics.mode -notin @("vector", "hybrid")) {
        throw "Context search diagnostics reported mode '$($searchDiagnostics.mode)' for embedding provider '$agentProvider'."
    }
}

Write-Host "Context hits: $(@($search.hits).Count)"
Write-Host "Search diagnostics: mode=$($searchDiagnostics.mode), provider=$($searchDiagnostics.model_provider), vector_hits=$($searchDiagnostics.vector_hit_count), lexical_hits=$($searchDiagnostics.lexical_hit_count), fallback=$($searchDiagnostics.lexical_fallback)"

Write-Step "Running symbol search"
$symbolBody = @{
    query = "DownloadAsync"
    repository_id = $repositoryId
    limit = 5
    kinds = @("Method")
    include_declarations = $true
    filters = @{}
} | ConvertTo-Json -Depth 8
$symbols = Invoke-RestMethod -Uri "$AgentAccessUrl/symbols/search" -Method Post -ContentType "application/json" -Body $symbolBody -TimeoutSec 30
if (@($symbols.symbols).Count -eq 0) {
    throw "Symbol search returned no symbols."
}
Write-Host "Symbol hits: $(@($symbols.symbols).Count)"

Write-Step "Running context package"
$packageBody = @{
    query = "DownloadAsync"
    repository_id = $repositoryId
    limit = 3
    max_characters = 4000
    include_relationships = $true
    relationship_limit = 8
    caller_limit = 2
    callee_limit = 2
    read_limit = 2
    write_limit = 2
} | ConvertTo-Json -Depth 8
$package = Invoke-RestMethod -Uri "$AgentAccessUrl/context/package" -Method Post -ContentType "application/json" -Body $packageBody -TimeoutSec 30
if (@($package.items).Count -eq 0) {
    throw "Context package returned no items."
}
Write-Host "Package items: $(@($package.items).Count)"

if (!$KeepFixture -and [System.IO.Path]::GetFullPath($RepositoryRoot).StartsWith([System.IO.Path]::GetFullPath((Join-Path $repoRoot ".codemesh-smoke")), [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Step "Cleaning generated fixture"
    Remove-Item -LiteralPath (Join-Path $repoRoot ".codemesh-smoke") -Recurse -Force
}

Write-Step "End-to-end smoke completed"
