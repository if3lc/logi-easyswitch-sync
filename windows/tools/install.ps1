<#
.SYNOPSIS
    Installs (or updates) the patched CleverSwitch build for the current Windows user.

.DESCRIPTION
    Per-user, no elevation. Verifies the exe, stops any running instance, backs up the current exe and
    Startup entry under <InstallDir>\backup, copies the new exe, writes run_cleverswitch.vbs into the
    user's Startup folder (hidden window, -vv, rotating log file) and launches it through that entry so
    the logon path is exercised right away.

.PARAMETER InstallDir
    Where cleverswitch.exe lives. Default: %LOCALAPPDATA%\Programs\CleverSwitch (upstream's location).

.PARAMETER Exe
    The exe to install. Default: ..\dist\cleverswitch.exe next to this script.

.PARAMETER NoStart
    Install and write the Startup entry, but do not launch the daemon now.
#>
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\CleverSwitch"),
    [string]$Exe = (Join-Path $PSScriptRoot "..\dist\cleverswitch.exe"),
    [switch]$NoStart
)
$ErrorActionPreference = "Stop"

$Exe = (Resolve-Path $Exe).Path
$startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$vbs = Join-Path $startup "run_cleverswitch.vbs"
$target = Join-Path $InstallDir "cleverswitch.exe"
$logs = Join-Path $InstallDir "logs"
$backup = Join-Path $InstallDir "backup"
$logPath = Join-Path $logs "cleverswitch.log"
New-Item -ItemType Directory -Force $InstallDir, $logs, $backup | Out-Null

$newVersion = & $Exe --version
if (-not $newVersion) { throw "$Exe did not report a version; refusing to install it." }
Write-Host "Installing: $newVersion"

$running = Get-Process -Name cleverswitch -ErrorAction SilentlyContinue
if ($running) {
    Write-Host ("Stopping cleverswitch.exe PIDs: " + ($running.Id -join ", "))
    $running | Stop-Process -Force -Confirm:$false
    Start-Sleep -Seconds 2
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (Test-Path $target) {
    $oldVersion = & $target --version
    Copy-Item $target (Join-Path $backup "cleverswitch-$stamp.exe") -Force
    Write-Host "Backed up current exe ($oldVersion) to backup\cleverswitch-$stamp.exe"
    $stockExe = Join-Path $backup "cleverswitch-1.5.4-stock.exe"
    if (($oldVersion -match "^cleverswitch 1\.5\.4 \(") -and -not (Test-Path $stockExe)) {
        Copy-Item $target $stockExe -Force
        Write-Host "Kept it as the stock reference: backup\cleverswitch-1.5.4-stock.exe"
    }
}
if (Test-Path $vbs) {
    Copy-Item $vbs (Join-Path $backup "run_cleverswitch.vbs.$stamp") -Force
    $stockVbs = Join-Path $backup "run_cleverswitch.vbs.stock"
    if (-not (Test-Path $stockVbs) -and -not ((Get-Content $vbs -Raw) -match "--log-file")) {
        Copy-Item $vbs $stockVbs -Force
    }
}

Copy-Item $Exe $target -Force

$lines = @(
    'Set WinScriptHost = CreateObject("WScript.Shell")',
    'WinScriptHost.CurrentDirectory = WinScriptHost.ExpandEnvironmentStrings("%USERPROFILE%")',
    ('WinScriptHost.Run Chr(34) & "' + $target + '" & Chr(34) & " -vv --log-file " & Chr(34) & "' + $logPath + '" & Chr(34), 0'),
    'Set WinScriptHost = Nothing'
)
New-Item -ItemType Directory -Force $startup | Out-Null
[IO.File]::WriteAllLines($vbs, $lines, (New-Object System.Text.ASCIIEncoding))
Write-Host "Startup entry written: $vbs"

if ($NoStart) { Write-Host "Not started (-NoStart)."; return }

Start-Process -FilePath "wscript.exe" -ArgumentList ('"' + $vbs + '"')
Start-Sleep -Seconds 4
Get-CimInstance Win32_Process -Filter "Name='cleverswitch.exe'" |
    Select-Object ProcessId, ParentProcessId, CommandLine | Format-Table -AutoSize -Wrap
if (Test-Path $logPath) {
    Write-Host "--- $logPath (tail) ---"
    Get-Content $logPath -Encoding UTF8 -Tail 5
}
