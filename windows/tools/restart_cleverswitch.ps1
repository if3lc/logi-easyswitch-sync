<#
.SYNOPSIS
    Stops every running CleverSwitch instance (exe build or "pythonw -m cleverswitch") and relaunches it
    exactly the way the Startup entry does (hidden window, -vv, rotating log file). No elevation needed.
#>
$ErrorActionPreference = "Stop"
$vbs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\run_cleverswitch.vbs"

$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "cleverswitch.exe" -or ($_.CommandLine -and $_.CommandLine -match "-m cleverswitch")
}
if ($running) {
    Write-Host ("Stopping: " + (($running | ForEach-Object { "$($_.Name)[$($_.ProcessId)]" }) -join ", "))
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

if (-not (Test-Path $vbs)) { throw "Startup entry not found: $vbs (run install.ps1 first)" }
Start-Process -FilePath "wscript.exe" -ArgumentList ('"' + $vbs + '"')
Start-Sleep -Seconds 5
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "cleverswitch.exe" -or ($_.CommandLine -and $_.CommandLine -match "-m cleverswitch")
} | Select-Object ProcessId, ParentProcessId, Name, CommandLine | Format-Table -AutoSize -Wrap
