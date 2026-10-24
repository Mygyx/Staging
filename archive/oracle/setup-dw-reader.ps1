# Crea un consumidor con CREATE SESSION y READ sobre las 11 tablas fuente.
$ErrorActionPreference = 'Stop'
$credentialPath = Join-Path $PSScriptRoot 'local\dw-reader-credential.xml'
if (Test-Path -LiteralPath $credentialPath) { throw 'Ya existe la credencial del lector DW.' }
$contract = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'contracts\staging_sources.json') | ConvertFrom-Json
if ($contract.schema -ne 'CHINOOK_STAGING' -or $contract.sources.Count -ne 11) { throw 'Contrato inesperado.' }
$grants = foreach ($source in $contract.sources) {
    if ($source.table -notmatch '^[A-Z][A-Z0-9_]{0,29}$') { throw 'Identificador invalido.' }
    "  execute immediate 'grant read on CHINOOK_STAGING.$($source.table) to CHINOOK_STG_READ';"
}
$randomBytes = New-Object byte[] 12
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $generator.GetBytes($randomBytes) } finally { $generator.Dispose() }
$generatedPassword = 'R9_' + ([System.BitConverter]::ToString($randomBytes).Replace('-', ''))
$sqlText = @"
whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set echo off verify off feedback off
alter session set container=XEPDB1;
declare
  v_count number;
begin
  select count(*) into v_count from dba_users where username='CHINOOK_STG_READ';
  if v_count <> 0 then raise_application_error(-20011, 'El lector DW ya existe; no se modifica.'); end if;
  execute immediate 'create user CHINOOK_STG_READ identified by "$generatedPassword"';
  execute immediate 'grant create session to CHINOOK_STG_READ';
$($grants -join "`n")
end;
/
exit success
"@
$sqlText | & (Get-Command sqlplus.exe -ErrorAction Stop).Source -L -S / as sysdba
if ($LASTEXITCODE -ne 0) { throw 'No se pudo configurar el lector DW.' }
$securePassword = ConvertTo-SecureString -String $generatedPassword -AsPlainText -Force
$credential = [System.Management.Automation.PSCredential]::new('CHINOOK_STG_READ', $securePassword)
$credential | Export-Clixml -LiteralPath $credentialPath
$generatedPassword = $null
$sqlText = $null
Write-Output 'CHINOOK_STG_READ creado con lectura de las 11 tablas. Credencial local cifrada, excluida de Git.'
