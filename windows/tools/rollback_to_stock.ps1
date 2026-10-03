<#
.SYNOPSIS
    Rolls CleverSwitch back to a backed-up exe and Startup entry (by default the untouched upstream
    1.5.4 saved by install.ps1), then relaunches. Logs, source and tools are left in place.

.PARAMETER InstallDir
    Where cleverswitch.exe lives. Default: %LOCALAPPDATA%\Programs\CleverSwitch.

.PARAMETER BackupExe
    File name under <InstallDir>\backup to restore. Default: cleverswitch-1.5.4-stock.exe.

.PARAMETER BackupVbs
    File name under <InstallDir>\backup to restore as the Startup entry. Default: run_cleverswitch.vbs.stock.
#>
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\CleverSwitch"),
    [string]$BackupExe = "cleverswitch-1.5.4-stock.exe",
    [string]$BackupVbs = "run_cleverswitch.vbs.stock"
)
$ErrorActionPreference = "Stop"
$backup = Join-Path $InstallDir "backup"
$startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"

$exeSrc = Join-Path $backup $BackupExe
$vbsSrc = Join-Path $backup $BackupVbs
if (-not (Test-Path $exeSrc)) { throw "Backup exe missing: $exeSrc" }
if (-not (Test-Path $vbsSrc)) { throw "Backup Startup entry missing: $vbsSrc" }

$running = Get-Process -Name cleverswitch -ErrorAction SilentlyContinue
if ($running) {
    Write-Host ("Stopping cleverswitch.exe PIDs: " + ($running.Id -join ", "))
    $running | Stop-Process -Force -Confirm:$false
    Start-Sleep -Seconds 2
}

Copy-Item $exeSrc (Join-Path $InstallDir "cleverswitch.exe") -Force
Copy-Item $vbsSrc (Join-Path $startup "run_cleverswitch.vbs") -Force
Write-Host "Restored $BackupExe and $BackupVbs."

& (Join-Path $InstallDir "cleverswitch.exe") --version
Start-Process -FilePath "wscript.exe" -ArgumentList ('"' + (Join-Path $startup "run_cleverswitch.vbs") + '"')
Start-Sleep -Seconds 4
Get-CimInstance Win32_Process -Filter "Name='cleverswitch.exe'" |
    Select-Object ProcessId, ParentProcessId, CommandLine | Format-Table -AutoSize -Wrap
