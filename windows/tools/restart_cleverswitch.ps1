<#
.SYNOPSIS
    Stops every running cleverswitch.exe and relaunches it exactly the way the Startup entry does
    (hidden window, -vv, rotating log file). No elevation needed.
#>
$ErrorActionPreference = "Stop"
$vbs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\run_cleverswitch.vbs"

$running = Get-Process -Name cleverswitch -ErrorAction SilentlyContinue
if ($running) {
    Write-Host ("Stopping cleverswitch.exe PIDs: " + ($running.Id -join ", "))
    $running | Stop-Process -Force -Confirm:$false
    Start-Sleep -Seconds 2
}

if (-not (Test-Path $vbs)) { throw "Startup entry not found: $vbs (run install.ps1 first)" }
Start-Process -FilePath "wscript.exe" -ArgumentList ('"' + $vbs + '"')
Start-Sleep -Seconds 4
Get-CimInstance Win32_Process -Filter "Name='cleverswitch.exe'" |
    Select-Object ProcessId, ParentProcessId, CommandLine | Format-Table -AutoSize -Wrap
