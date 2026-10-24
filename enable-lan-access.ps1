param(
    [Parameter(Mandatory=$true)][string]$LocalAddress,
    [Parameter(Mandatory=$true)][string]$AllowedSubnet
)
$ErrorActionPreference = 'Stop'
$assigned = Get-NetIPAddress -AddressFamily IPv4 -IPAddress $LocalAddress -ErrorAction Stop
if ($assigned.IPAddress -like '127.*') { throw 'Use la IPv4 de la red local.' }
if ($AllowedSubnet -notmatch '^\d{1,3}(\.\d{1,3}){3}/\d{1,2}$') { throw 'Especifique la subred permitida en CIDR.' }
$ruleName = 'ChinookStagingOracleLAN'
$existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existing) { throw 'La regla ya existe; revise sus parametros antes de modificarla.' }
New-NetFirewallRule -Name $ruleName -DisplayName 'Chinook Staging - Oracle desde LAN' `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 1521 `
    -LocalAddress $LocalAddress -RemoteAddress $AllowedSubnet `
    -InterfaceAlias $assigned.InterfaceAlias -Profile Any -ErrorAction Stop | Out-Null
$created = Get-NetFirewallRule -Name $ruleName -ErrorAction Stop
if (-not $created -or $created.Action -ne 'Allow') { throw 'No se pudo verificar la regla del firewall.' }
Write-Output "Oracle TCP/1521 habilitado solo hacia $LocalAddress desde $AllowedSubnet."
