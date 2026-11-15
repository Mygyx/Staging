$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_python_comun.ps1')
if (-not (Test-Path -LiteralPath (Join-Path $script:StagingRoot '.env.reader'))) { throw 'Configurar .env.reader para verificar el acceso del DW.' }
Invoke-StagingPython -PythonArguments @('scripts/staging_flow.py','--validate-only')
Invoke-StagingPython -PythonArguments @('scripts/staging_contract.py','--check','--env-file','.env.reader')
