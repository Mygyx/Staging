param([switch]$RevealPassword, [string]$HostAddress = '192.168.0.250')
$ErrorActionPreference = 'Stop'
$credential = Import-Clixml -LiteralPath (Join-Path $PSScriptRoot 'local\dw-reader-credential.xml')
$details = [ordered]@{
    Host = $HostAddress
    Port = 1521
    Service = 'XEPDB1'
    Schema = 'CHINOOK_STAGING'
    User = $credential.UserName
    DSN = "${HostAddress}:1521/XEPDB1"
}
if ($RevealPassword) { $details['Password'] = $credential.GetNetworkCredential().Password }
[pscustomobject]$details
if (-not $RevealPassword) { Write-Output 'Para ver la clave al compartirla por un canal privado: .\show-dw-connection.ps1 -RevealPassword' }
