[CmdletBinding(DefaultParameterSetName = 'Serve')]
param(
    [Parameter(ParameterSetName = 'Serve')][switch]$Serve,
    [Parameter(ParameterSetName = 'RunOnce')][switch]$RunOnce,
    [Parameter(ParameterSetName = 'ValidateOnly')][switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Crea .venv e instala requirements.txt siguiendo el README.'
}
$flowArgs = @((Join-Path $PSScriptRoot 'scripts\staging_flow.py'))
if ($ValidateOnly) { $flowArgs += '--validate-only' }
elseif ($RunOnce) { $flowArgs += '--run-once' }
else { $flowArgs += '--serve' }
& $pythonPath @flowArgs
$resultCode = $LASTEXITCODE
if ($resultCode -ne 0) { throw "Prefect termino con codigo $resultCode" }
