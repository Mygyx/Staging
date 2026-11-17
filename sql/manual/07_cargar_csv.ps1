$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_python_comun.ps1')
Write-Output 'Se ejecutara el flujo original: leer CSV, cargar chinook_staging y validar. Requiere preparacion previa.'
Invoke-StagingPython -PythonArguments @('scripts/staging_flow.py','--run-once')
