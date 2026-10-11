<#
.SYNOPSIS
    Installs (or updates) the patched CleverSwitch for the current Windows user.

.DESCRIPTION
    Per-user, no elevation. Two modes:

      Source (default)  A virtual environment made with an official, Authenticode-signed python.exe
                        runs the patched package: "<InstallDir>\venv\Scripts\pythonw.exe -m cleverswitch".
                        This is the mode that works with Smart App Control / App Control for Business
                        switched on: the interpreter is signed and hidapi.dll is the same file the
                        upstream release ships, so nothing unknown has to be allowed. Needs an official
                        Python 3.10+ from python.org (auto-detected via the py launcher or PATH).

      Exe               Copies the prebuilt PyInstaller exe from ..\dist. Simplest, but a locally built
                        exe has no cloud reputation and is blocked when Smart App Control is on.

    Either way the script stops any running instance, backs up the current exe and Startup entry under
    <InstallDir>\backup, writes run_cleverswitch.vbs into the user's Startup folder (hidden, -vv, rotating
    log file) and launches it through that entry so the logon path is exercised right away.

.PARAMETER Mode
    Source or Exe. Default Source.

.PARAMETER InstallDir
    Where the runtime lives. Default: %LOCALAPPDATA%\Programs\CleverSwitch (upstream's location).

.PARAMETER SourceTree
    The patched CleverSwitch tree to install in Source mode. Default: ..\..\cleverswitch in this repository.

.PARAMETER Python
    Official python.exe to build the venv with. Default: auto-detect (py -3, then python on PATH).

.PARAMETER Version
    Version string recorded for the package in Source mode (the tree has no git metadata).

.PARAMETER Exe
    The exe to install in Exe mode. Default: ..\dist\cleverswitch.exe next to this script.

.PARAMETER NoStart
    Install and write the Startup entry, but do not launch the daemon now.
#>
param(
    [ValidateSet("Source", "Exe")] [string]$Mode = "Source",
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\CleverSwitch"),
    [string]$SourceTree = (Join-Path $PSScriptRoot "..\..\cleverswitch"),
    [string]$Python = "",
    [string]$Version = "1.5.4+reconnect.3",
    [string]$Exe = (Join-Path $PSScriptRoot "..\dist\cleverswitch.exe"),
    [switch]$NoStart
)
$ErrorActionPreference = "Stop"

function Get-CleverSwitchProcesses {
    # The exe build is named cleverswitch.exe; the source build is pythonw.exe -m cleverswitch.
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "cleverswitch.exe" -or ($_.CommandLine -and $_.CommandLine -match "-m cleverswitch")
    }
}

function Stop-CleverSwitch {
    $running = Get-CleverSwitchProcesses
    if ($running) {
        Write-Host ("Stopping running instance(s): " + (($running | ForEach-Object { "$($_.Name)[$($_.ProcessId)]" }) -join ", "))
        $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
    }
}

function Find-OfficialPython {
    param([string]$Preferred)
    if ($Preferred) { return (Resolve-Path $Preferred).Path }
    $candidates = @()
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { try { $candidates += (& $py.Source -3 -c "import sys; print(sys.executable)" 2>$null) } catch { } }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notmatch "WindowsApps") { $candidates += $python.Source }
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    throw "No official python.exe found. Install Python 3.10+ from python.org or pass -Python <path>."
}

$startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$vbs = Join-Path $startup "run_cleverswitch.vbs"
$target = Join-Path $InstallDir "cleverswitch.exe"
$logs = Join-Path $InstallDir "logs"
$backup = Join-Path $InstallDir "backup"
$logPath = Join-Path $logs "cleverswitch.log"
New-Item -ItemType Directory -Force $InstallDir, $logs, $backup | Out-Null

# ── Stop + back up what is there ──────────────────────────────────────────────
Stop-CleverSwitch
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (Test-Path $target) {
    $oldVersion = $null
    try { $oldVersion = & $target --version 2>$null } catch { $oldVersion = "(blocked or not runnable)" }
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

# ── Install ───────────────────────────────────────────────────────────────────
if ($Mode -eq "Exe") {
    $Exe = (Resolve-Path $Exe).Path
    $newVersion = & $Exe --version
    if (-not $newVersion) { throw "$Exe did not report a version; refusing to install it." }
    Copy-Item $Exe $target -Force
    $command = '"' + $target + '"'
}
else {
    $SourceTree = (Resolve-Path $SourceTree).Path
    if (-not (Test-Path (Join-Path $SourceTree "pyproject.toml"))) { throw "Not a CleverSwitch source tree: $SourceTree" }
    $basePython = Find-OfficialPython -Preferred $Python
    $sig = Get-AuthenticodeSignature $basePython
    Write-Host ("Base interpreter: " + $basePython + " [" + $sig.Status + ": " + $sig.SignerCertificate.Subject + "]")
    $venv = Join-Path $InstallDir "venv"
    $venvPy = Join-Path $venv "Scripts\python.exe"
    if (-not (Test-Path $venvPy)) {
        Write-Host "Creating venv at $venv"
        & $basePython -m venv $venv
    }
    $env:SETUPTOOLS_SCM_PRETEND_VERSION = $Version
    Write-Host "Installing $SourceTree as $Version"
    & $venvPy -m pip install --quiet --disable-pip-version-check --force-reinstall --no-deps $SourceTree
    & $venvPy -m pip install --quiet --disable-pip-version-check "pyyaml>=6.0" "hid>=1.0.9"
    Remove-Item Env:\SETUPTOOLS_SCM_PRETEND_VERSION -ErrorAction SilentlyContinue
    # transport.py adds <prefix>\Scripts to the DLL search path; same bytes as the upstream release ships.
    Copy-Item (Join-Path $SourceTree "hidapi.dll") (Join-Path $venv "Scripts\hidapi.dll") -Force
    $newVersion = & $venvPy -m cleverswitch --version
    if (-not $newVersion) { throw "python -m cleverswitch --version failed inside $venv" }
    $command = '"' + (Join-Path $venv "Scripts\pythonw.exe") + '" -m cleverswitch'
}
Write-Host "Installed: $newVersion ($Mode mode)"

# ── Startup entry ─────────────────────────────────────────────────────────────
$lines = @(
    'Set WinScriptHost = CreateObject("WScript.Shell")',
    'WinScriptHost.CurrentDirectory = WinScriptHost.ExpandEnvironmentStrings("%USERPROFILE%")',
    ('WinScriptHost.Run "' + ($command -replace '"', '""') + ' -vv --log-file ""' + $logPath + '""", 0'),
    'Set WinScriptHost = Nothing'
)
New-Item -ItemType Directory -Force $startup | Out-Null
[IO.File]::WriteAllLines($vbs, $lines, (New-Object System.Text.ASCIIEncoding))
Write-Host "Startup entry written: $vbs"
Get-Content $vbs | Select-Object -Index 2

if ($NoStart) { Write-Host "Not started (-NoStart)."; return }

Start-Process -FilePath "wscript.exe" -ArgumentList ('"' + $vbs + '"')
Start-Sleep -Seconds 5
Get-CleverSwitchProcesses | Select-Object ProcessId, ParentProcessId, Name, CommandLine | Format-Table -AutoSize -Wrap
if (Test-Path $logPath) {
    Write-Host "--- $logPath (tail) ---"
    Get-Content $logPath -Encoding UTF8 -Tail 5
}
