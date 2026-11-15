# Ayuda de ejecucion: usa el ETL existente y no aprovisiona PostgreSQL.
$script:StagingRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Invoke-StagingPython {
    param([string[]]$PythonArguments)
    $python = Join-Path $script:StagingRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Crear .venv e instalar requirements.txt siguiendo el README.' }
    if (-not (Test-Path -LiteralPath (Join-Path $script:StagingRoot '.env'))) { throw 'Configurar .env antes de cargar o validar.' }
    if (-not $env:PREFECT_API_URL) { throw 'Configurar PREFECT_API_URL en esta terminal; ver el README. Este ayudante no inicia un servidor.' }
    if (-not $env:PREFECT_HOME) { $env:PREFECT_HOME = Join-Path $script:StagingRoot 'local\prefect' }
    New-Item -ItemType Directory -Path $env:PREFECT_HOME -Force | Out-Null
    $previousPreference = $ErrorActionPreference
    Push-Location $script:StagingRoot
    try {
        # Prefect emite INFO por stderr. El fallo se decide por el codigo de salida.
        $ErrorActionPreference = 'Continue'
        & $python @PythonArguments 2>&1 | ForEach-Object { Write-Output ([string]$_) }
        $result = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
        Pop-Location
    }
    if ($result -ne 0) { throw "El comando Python termino con codigo $result. Revisar el error antes de continuar." }
}
