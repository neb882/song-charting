# run-hooks.ps1: runs the Windows CI hooks (the `windows` job of .github/workflows/ci.yml).
#
#   ./packaging/ci/run-hooks.ps1 windows
#
# Runs every packaging/ci/windows.d/*.ps1 in name order (ordinal), each in a fresh pwsh from the repository's root,
# and prints a header per hook and its time. A hook runs with $ErrorActionPreference = 'Stop', Set-StrictMode -Version
# Latest and $PSNativeCommandUseErrorActionPreference = $true, PowerShell's `bash -euo pipefail`: an error, or a native
# command that exits non-zero, stops it. It fails by stopping that way, or by ending with `exit N` (N not 0) or a
# non-zero $LASTEXITCODE. The first hook that fails stops the run, which exits with its code. Exits 2, running nothing,
# when windows.d is missing or holds anything but README.txt and *.ps1 files. The hook contract (the numbering, the
# CI_* variables, and what a hook must check itself) is windows.d/README.txt.
#
# Before the first hook it sets what the caller did not (so it also runs by hand): CI_PY (python on PATH), and CI_TMP
# and CI_ART (under $env:RUNNER_TEMP, or the temp folder), all absolute, and makes the two folders. There is no CI_CLIP
# on Windows: the job installs no numpy or soundfile.
param([Parameter(Position = 0)][string]$Platform)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $false   # this script reads the hooks' exit codes itself

if ($Platform -ne 'windows') {
    [Console]::Error.WriteLine('usage: run-hooks.ps1 windows')
    exit 2
}
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$dir = Join-Path $PSScriptRoot "$Platform.d"

# The hooks: the *.ps1 files directly in windows.d. Anything else there but README.txt (another extension, no
# extension, a hidden file, a folder) is a hook in the wrong shape, which would otherwise be skipped without a word.
if (-not (Test-Path -LiteralPath $dir -PathType Container)) {
    [Console]::Error.WriteLine("run-hooks: no hook folder $dir")
    exit 2
}
$names = [Collections.Generic.List[string]]::new()
$stray = [Collections.Generic.List[string]]::new()
foreach ($entry in @(Get-ChildItem -LiteralPath $dir -Force)) {
    $file = -not $entry.PSIsContainer
    if ($file -and $entry.Name -ceq 'README.txt') { continue }
    if ($file -and $entry.Extension -eq '.ps1' -and -not $entry.Name.StartsWith('.')) {
        $names.Add($entry.Name)
    } else {
        $stray.Add("$Platform.d/$($entry.Name)")
    }
}
if ($stray.Count -gt 0) {
    $stray.Sort([StringComparer]::Ordinal)
    foreach ($s in $stray) { [Console]::Error.WriteLine("run-hooks: not a hook: $s") }
    [Console]::Error.WriteLine("run-hooks: a hook is a NN-name.ps1 file directly in $Platform.d, and README.txt the " +
        'only other entry')
    exit 2
}
$names.Sort([StringComparer]::Ordinal)

$base = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
if (-not $env:CI_PY) {
    $python = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $python) {
        [Console]::Error.WriteLine('run-hooks: no CI_PY, and no python on PATH')
        exit 2
    }
    $env:CI_PY = $python.Source
}
if (-not $env:CI_TMP) { $env:CI_TMP = Join-Path $base 'ci-tmp' }
if (-not $env:CI_ART) { $env:CI_ART = Join-Path $base 'ci-artifacts' }
$env:CI_TMP = (New-Item -ItemType Directory -Force -Path $env:CI_TMP).FullName
$env:CI_ART = (New-Item -ItemType Directory -Force -Path $env:CI_ART).FullName
foreach ($name in 'CI_PY', 'CI_TMP', 'CI_ART') {
    Write-Host "$name=$([Environment]::GetEnvironmentVariable($name))"
}

if ($names.Count -eq 0) {
    Write-Host 'no Windows hooks'
    exit 0
}

# The child's whole program: the strict settings, then the hook (named by CI_HOOK, so no quoting), then its code. It
# runs with -OutputFormat Text: -EncodedCommand alone writes warnings and other streams as CLIXML when stderr is a pipe.
$program = @'
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true
$global:LASTEXITCODE = 0
try {
    & $env:CI_HOOK
} catch {
    [Console]::Error.WriteLine(($_ | Out-String).TrimEnd())
    [Console]::Error.WriteLine($_.ScriptStackTrace)
    exit 1
}
exit $LASTEXITCODE
'@
$encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($program))
$pwsh = (Get-Process -Id $PID).Path

Set-Location -LiteralPath $root
$passed = @()
foreach ($name in $names) {
    $label = "$Platform.d/$name"
    Write-Host ''
    Write-Host "==== hook $label"
    $env:CI_HOOK = Join-Path $dir $name
    $clock = [Diagnostics.Stopwatch]::StartNew()
    & $pwsh -NoProfile -NonInteractive -OutputFormat Text -EncodedCommand $encoded
    $code = $LASTEXITCODE
    $took = [int]$clock.Elapsed.TotalSeconds
    if ($code -ne 0) {
        Write-Host "==== hook $label FAILED (exit $code) after $took s"
        Write-Host "hooks passed before it: $(if ($passed) { $passed -join ' ' } else { 'none' })"
        exit $code
    }
    Write-Host "==== hook $label ok in $took s"
    $passed += "$name ${took}s"
}
Remove-Item Env:CI_HOOK
Write-Host ''
Write-Host "all $($names.Count) Windows hooks passed: $($passed -join ' ')"
