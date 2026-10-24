param([switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Crea .venv e instala requirements.txt siguiendo el README.'
}
$credentialPath = Join-Path $PSScriptRoot 'local\oracle-credential.xml'
$savedCredential = $null
if (Test-Path -LiteralPath $credentialPath) {
    $savedCredential = Import-Clixml -LiteralPath $credentialPath
}
if (-not $env:ORACLE_USER) {
    $env:ORACLE_USER = if ($savedCredential) { $savedCredential.UserName } else { 'INVACOM_STG' }
}
if (-not $env:ORACLE_DSN) { $env:ORACLE_DSN = 'localhost:1521/XEPDB1' }
$providedPassword = -not [string]::IsNullOrEmpty($env:ORACLE_PASSWORD)
try {
    if (-not $providedPassword) {
        $securePassword = if ($savedCredential -and $savedCredential.UserName -eq $env:ORACLE_USER) {
            $savedCredential.Password
        } else { Read-Host "Contrasena Oracle para $env:ORACLE_USER" -AsSecureString }
        $env:ORACLE_PASSWORD = [System.Net.NetworkCredential]::new('', $securePassword).Password
    }
    $flowArgs = @((Join-Path $PSScriptRoot 'scripts\staging_flow.py'))
    if ($ValidateOnly) { $flowArgs += '--validate-only' }
    & $pythonPath @flowArgs
    $resultCode = $LASTEXITCODE
} finally {
    if (-not $providedPassword) { Remove-Item Env:ORACLE_PASSWORD -ErrorAction SilentlyContinue }
}
if ($resultCode -ne 0) { throw "Prefect termino con codigo $resultCode" }
