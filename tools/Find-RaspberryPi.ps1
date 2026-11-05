#requires -Version 5.1
<#
.SYNOPSIS
Finds SSH devices on a local IPv4 subnet and optionally identifies a Pi over SSH.
.EXAMPLE
.\Find-RaspberryPi.ps1
.EXAMPLE
.\Find-RaspberryPi.ps1 -Subnet 192.168.1 -SshUser emanuel
.NOTES
Scans a /24 (addresses .1 through .254). Use only on networks you administer.
SshUser enables public-key authentication only; passwords are never attempted.
#>
[CmdletBinding()]
param(
    [ValidatePattern('^(\d{1,3}\.){2}\d{1,3}$')]
    [string]$Subnet,
    [string]$SshUser,
    [ValidateRange(100,10000)] [int]$TimeoutMs = 600,
    [ValidateRange(1,128)] [int]$Concurrency = 32
)
$ErrorActionPreference = 'Stop'
if (-not $Subnet) {
    $route = Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' |
        Sort-Object RouteMetric | Select-Object -First 1
    if (-not $route) { throw 'No default IPv4 route found. Supply -Subnet, for example 192.168.1.' }
    $address = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1
    if (-not $address) { throw 'No IPv4 address found. Supply -Subnet.' }
    if ($address.PrefixLength -ne 24) {
        throw 'Automatic discovery supports /24 networks. Supply -Subnet to scan a specific /24.'
    }
    $Subnet = $address.IPAddress -replace '\.\d+$', ''
}
foreach ($octet in $Subnet.Split('.')) {
    if ([int]$octet -gt 255) { throw 'Invalid subnet octet.' }
}
if ($SshUser -and -not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    throw 'OpenSSH client is required for -SshUser. Run without it for port discovery.'
}
Write-Host "Scanning $Subnet.1-254 for SSH..."
$open = @()
for ($start = 1; $start -le 254; $start += $Concurrency) {
    $pending = @()
    try {
        $pending = @(foreach ($n in $start..([Math]::Min(254, $start + $Concurrency - 1))) {
            $client = New-Object System.Net.Sockets.TcpClient
            [pscustomobject]@{ IP = "$Subnet.$n"; Client = $client; Task = $client.ConnectAsync("$Subnet.$n", 22) }
        })
        $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
        while ([DateTime]::UtcNow -lt $deadline -and @($pending | Where-Object { -not $_.Task.IsCompleted }).Count) {
            Start-Sleep -Milliseconds 20
        }
        foreach ($item in $pending) {
            if ($item.Task.Status -eq 'RanToCompletion' -and $item.Client.Connected) { $open += $item.IP }
        }
    } finally {
        foreach ($item in $pending) { $item.Client.Dispose() }
    }
}
if (-not $open.Count) { Write-Host 'No devices with TCP port 22 open were found.'; return }
foreach ($ip in $open) {
    $name = ''
    try {
        $lookup = [System.Net.Dns]::GetHostEntryAsync($ip)
        if ($lookup.Wait(500)) { $name = $lookup.Result.HostName }
    } catch { }
    $status = 'SSH open; identity unconfirmed'
    $details = ''
    if ($name -match 'raspberry|raspi') { $status = 'Possible Raspberry Pi (hostname)' }
    if ($SshUser) {
        # Accept new host keys only into a dedicated file; changed keys remain rejected.
        $knownHosts = Join-Path $PSScriptRoot '.rpi-known-hosts'
        $remote = 'cat /proc/device-tree/model 2>/dev/null; echo; hostname; cat /etc/os-release 2>/dev/null'
        $details = (& ssh -n -o BatchMode=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o PreferredAuthentications=publickey -o ConnectionAttempts=1 -o ConnectTimeout=3 -o StrictHostKeyChecking=accept-new -o "UserKnownHostsFile=$knownHosts" -l $SshUser $ip $remote 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -eq 0) {
            $status = 'SSH connected; not identified as a Pi'
            if ($details -match 'Raspberry Pi') { $status = 'Raspberry Pi confirmed' }
        } else { $status = 'SSH open; key login failed (identity unconfirmed)' }
    }
    [pscustomobject]@{ Address = $ip; Hostname = $name; Status = $status; Details = $details }
}
