# Opcional: Oracle XE local en Windows, con autenticacion OS de administrador.
# No reemplaza usuarios existentes. Solo crea CHINOOK_STAGING dentro de XEPDB1.
$ErrorActionPreference = 'Stop'
$credentialPath = Join-Path $PSScriptRoot 'local\oracle-credential.xml'
if (Test-Path -LiteralPath $credentialPath) { throw 'Ya hay credenciales locales. No se reemplazan.' }
$sqlplusCommand = Get-Command sqlplus.exe -ErrorAction Stop
$randomBytes = New-Object byte[] 12
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $generator.GetBytes($randomBytes) } finally { $generator.Dispose() }
$generatedPassword = 'A9_' + ([System.BitConverter]::ToString($randomBytes).Replace('-', ''))
$sqlText = @"
whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set echo off verify off feedback off
alter session set container=XEPDB1;
declare
  v_count number;
begin
  select count(*) into v_count from dba_users where username='CHINOOK_STAGING';
  if v_count <> 0 then
    raise_application_error(-20010, 'CHINOOK_STAGING ya existe; no se modifica.');
  end if;
  execute immediate 'create user CHINOOK_STAGING identified by "$generatedPassword" default tablespace USERS quota 50M on USERS';
  execute immediate 'grant create session, create table to CHINOOK_STAGING';
end;
/
exit success
"@
# SQLPlus recibe la clave por stdin; no se escribe en SQL, logs ni argumentos.
$sqlText | & $sqlplusCommand.Source -L -S / as sysdba
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el usuario Oracle; revise el mensaje anterior.' }
$securePassword = ConvertTo-SecureString -String $generatedPassword -AsPlainText -Force
$credential = [System.Management.Automation.PSCredential]::new('CHINOOK_STAGING', $securePassword)
New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot 'local') -Force | Out-Null
$credential | Export-Clixml -LiteralPath $credentialPath
$generatedPassword = $null
$sqlText = $null
Write-Output 'CHINOOK_STAGING creado en XEPDB1. Credencial cifrada con Windows en local/ (excluido de Git).'
