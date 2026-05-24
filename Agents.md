# AGENTS.md

## Environment

This repo is usually worked on from JetBrains Rider on Windows with PowerShell.

Available CLI tools:
- `rg`
- `git`
- `dotnet` with .NET 10 SDK
- `python` 3.14
- `uv`
- `ruff`
- `pytest`
- `jq`
- `gh`
- `docker`
- `docker compose`
- `7z`

Notes:
- If a newly installed command is not visible, refresh PATH from persisted values:
  ```powershell
  $env:Path = "$([Environment]::GetEnvironmentVariable('Path', 'Machine'));$([Environment]::GetEnvironmentVariable('Path', 'User'))"