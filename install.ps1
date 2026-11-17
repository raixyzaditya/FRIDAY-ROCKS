<#
  Friday installer for Windows. Run it with:   install.bat
  (or: powershell -ExecutionPolicy Bypass -File install.ps1)

  What it does, in order:
    1. finds Python 3.10+ (or tells you how to get it)
    2. makes a virtual environment in this folder (.venv) unless one exists
    3. installs Friday and its libraries into it         (pip install -e .)
    4. creates Voice\Config.py from the example if you don't have one
    5. creates a small 'friday' command in  %USERPROFILE%\.friday\bin
    6. adds that folder to YOUR user PATH (no admin needed, nothing system-wide)

  Options:
    -DryRun     show what would happen, change nothing
    -SkipDeps   don't run pip (for a quick re-install of just the command)
    -NoPath     don't touch PATH
    -Prefix X   put the command in X\bin instead
  Undo with uninstall.bat.
#>
param(
    [switch]$DryRun,
    [switch]$SkipDeps,
    [switch]$NoPath,
    [string]$Prefix = (Join-Path $env:USERPROFILE ".friday")
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Say([string]$Message) { Write-Host "[Friday] $Message" }
function Fail([string]$Message) { Write-Host "[Friday] ERROR: $Message" -ForegroundColor Red; exit 1 }
function Step([string]$Message, [scriptblock]$Action) {
    if ($DryRun) { Say "(dry run) would: $Message" } else { Say $Message; & $Action }
}

# --- 1. Python 3.10+ ------------------------------------------------------------------------------
function Find-Python {
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"  # a missing/stub python prints to stderr; that must not abort us
    try {
        $options = @(@("py", "-3.12"), @("py", "-3.11"), @("py", "-3.10"), @("py", "-3"), @("python"))
        foreach ($o in $options) {
            $exe = $o[0]
            $rest = @()
            if ($o.Count -gt 1) { $rest = @($o[1..($o.Count - 1)]) }
            if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
            $version = & $exe @rest -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version) {
                if ([version]($version | Select-Object -First 1) -ge [version]"3.10") { return , (@($exe) + $rest) }
            }
        }
        return $null
    } finally { $ErrorActionPreference = $saved }
}

$py = Find-Python
if (-not $py) {
    Fail "Python 3.10 or newer wasn't found.`n         Install it with:  winget install Python.Python.3.12`n         then open a new terminal and run install.bat again."
}
$pyExe = $py[0]
$pyArgs = @()
if ($py.Count -gt 1) { $pyArgs = @($py[1..($py.Count - 1)]) }
Say "Using Python: $($py -join ' ')"

# --- 2. virtual environment -----------------------------------------------------------------------
$venv = Join-Path $Root ".venv"
$venvPy = Join-Path $venv "Scripts\python.exe"
if (Test-Path $venvPy) {
    Say "Using the existing virtual environment at $venv"
} else {
    Step "create a virtual environment at $venv" {
        & $pyExe @pyArgs -m venv $venv
        if ($LASTEXITCODE -ne 0) { Fail "Couldn't create the virtual environment." }
    }
}

# --- 3. Friday + libraries ------------------------------------------------------------------------
if ($SkipDeps) {
    Say "Skipping the library install (-SkipDeps)."
} else {
    Step "install Friday and its libraries (the first time this is a large download, about 1 GB or more, for PyTorch/Whisper: 5-15 minutes)" {
        & $venvPy -m pip install --upgrade pip
        & $venvPy -m pip install -e $Root
        if ($LASTEXITCODE -ne 0) { Fail "Installing Friday failed. The error from pip is just above." }
    }
}

# --- 4. Config.py ---------------------------------------------------------------------------------
$config = Join-Path $Root "Voice\Config.py"
$example = Join-Path $Root "Voice\Config.example.py"
if (Test-Path $config) {
    Say "Voice\Config.py already exists. Leaving it alone."
} else {
    Step "create Voice\Config.py from the example" { Copy-Item $example $config }
}

# --- 5. the 'friday' command ----------------------------------------------------------------------
$bin = Join-Path $Prefix "bin"
$shim = Join-Path $bin "friday.cmd"
$exe = Join-Path $venv "Scripts\friday.exe"
Step "create the 'friday' command at $shim" {
    New-Item -ItemType Directory -Force -Path $bin | Out-Null
    Set-Content -Path $shim -Value "@echo off`r`n`"$exe`" %*" -Encoding OEM
}

# --- 6. PATH (this user only; read raw so other %VARIABLES% entries are preserved) -----------------
function Get-UserPath {
    (Get-Item "HKCU:\Environment").GetValue("Path", "", [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
}
function Test-PathEntry([string]$PathValue, [string]$Dir) {
    $want = $Dir.TrimEnd('\').ToLowerInvariant()
    foreach ($p in $PathValue -split ';') { if ($p.Trim().TrimEnd('\').ToLowerInvariant() -eq $want) { return $true } }
    return $false
}

if ($NoPath) {
    Say "Not touching PATH (-NoPath). Add this folder to your PATH yourself: $bin"
} else {
    $current = Get-UserPath
    if (Test-PathEntry $current $bin) {
        Say "$bin is already on your PATH."
    } else {
        Step "add $bin to your user PATH" {
            $new = if ($current) { $current.TrimEnd(';') + ";" + $bin } else { $bin }
            Set-ItemProperty -Path "HKCU:\Environment" -Name Path -Value $new -Type ExpandString
            # Setting a user variable the .NET way also tells Windows the environment changed,
            # so terminals opened from now on see the new PATH without logging out.
            [Environment]::SetEnvironmentVariable("FRIDAY_HOME", $Root, "User")
            $env:Path = $env:Path.TrimEnd(';') + ";" + $bin
        }
    }
}

Write-Host ""
if ($DryRun) {
    Say "Dry run finished. Nothing was changed."
} else {
    Say "Done."
    Say "Open a NEW terminal, then:   friday --setup   (once, to enter your Groq key)"
    Say "                             friday           (to start her)"
}
