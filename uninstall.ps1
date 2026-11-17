<#
  Removes the 'friday' command and its PATH entry. Run with:   uninstall.bat

  It does NOT delete this project folder, the .venv, your Config.py, or Friday's data
  (memory, reminders, contacts, Google login). Delete those yourself if you want them gone.

  Options:  -DryRun (show only)   -Prefix X (if you installed with a different -Prefix)
#>
param(
    [switch]$DryRun,
    [string]$Prefix = (Join-Path $env:USERPROFILE ".friday")
)

$ErrorActionPreference = "Stop"
function Say([string]$Message) { Write-Host "[Friday] $Message" }
function Step([string]$Message, [scriptblock]$Action) {
    if ($DryRun) { Say "(dry run) would: $Message" } else { Say $Message; & $Action }
}

$bin = Join-Path $Prefix "bin"
$key = "HKCU:\Environment"
$raw = (Get-Item $key).GetValue("Path", "", [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
$want = $bin.TrimEnd('\').ToLowerInvariant()
$kept = @($raw -split ';' | Where-Object { $_.Trim() -ne "" -and $_.Trim().TrimEnd('\').ToLowerInvariant() -ne $want })

if ($kept.Count -ne @($raw -split ';' | Where-Object { $_.Trim() -ne "" }).Count) {
    Step "remove $bin from your user PATH" {
        Set-ItemProperty -Path $key -Name Path -Value ($kept -join ';') -Type ExpandString
        [Environment]::SetEnvironmentVariable("FRIDAY_HOME", $null, "User")  # also tells Windows the environment changed
    }
} else {
    Say "$bin wasn't on your PATH."
}

if (Test-Path $bin) {
    Step "delete $bin" { Remove-Item -Recurse -Force $bin }
} else {
    Say "$bin doesn't exist."
}
Say $(if ($DryRun) { "Dry run finished. Nothing was changed." } else { "Done. Open a new terminal; 'friday' is gone." })
