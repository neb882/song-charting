# 30-shortcut.ps1 (M4-03): the Start-menu shortcut's writer (songcharter.winshortcut), checked by Windows itself.
#   1. tests/test_winshortcut.py: LnkParse3 reads a written link back exactly;
#   2. a .lnk shaped like the real one, written by winshortcut: target %windir%\System32\cmd.exe (the environment
#      block), arguments /c "echo ok> %TEMP%\lnk-ok.txt || pause". The pass: Start-Process on it creates lnk-ok.txt
#      within 10 s, which only happens when Windows resolved the link and launched it. Then the link is written again
#      over the first (a reinstall) and must launch again.
# WScript.Shell's reading of the link (TargetPath, Arguments, WorkingDirectory) is printed for diagnosis only.
# Run by packaging/ci/run-hooks.ps1 (strict mode, a native command that fails stops it); uses CI_PY, CI_TMP, CI_ART.

& $env:CI_PY -m pytest -q -rs -p no:cacheprovider --basetemp="$env:CI_TMP\pt-shortcut" tests/test_winshortcut.py

$lnk = Join-Path $env:CI_TMP 'songcharter-test.lnk'
$ok = Join-Path $env:TEMP 'lnk-ok.txt'
$writer = Join-Path $env:CI_TMP 'write_lnk.py'
Set-Content -LiteralPath $writer -Encoding utf8 -Value @'
import os, sys
from songcharter import winshortcut
winshortcut.write(sys.argv[1], r"%windir%\System32\cmd.exe", os.environ["LNK_ARGS"], os.environ["USERPROFILE"],
                  os.environ["windir"] + r"\System32\wsl.exe")
'@
$env:LNK_ARGS = '/c "echo ok> %TEMP%\lnk-ok.txt || pause"'
$env:PYTHONPATH = (Get-Location).Path   # songcharter from the repository's root

foreach ($round in 1, 2) {
    Remove-Item -LiteralPath $ok -ErrorAction SilentlyContinue
    & $env:CI_PY $writer $lnk
    $sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    Write-Host "round $round, WScript.Shell reads (diagnosis only): TargetPath=$($sc.TargetPath)"
    Write-Host "  Arguments=$($sc.Arguments)"
    Write-Host "  WorkingDirectory=$($sc.WorkingDirectory) IconLocation=$($sc.IconLocation)"
    Start-Process -FilePath $lnk
    $deadline = (Get-Date).AddSeconds(10)
    while (-not (Test-Path -LiteralPath $ok) -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 200 }
    if (-not (Test-Path -LiteralPath $ok)) {
        [Console]::Error.WriteLine("30-shortcut: round ${round}: Windows did not run the link within 10 s (no $ok)")
        Copy-Item -LiteralPath $lnk -Destination (Join-Path $env:CI_ART 'songcharter-test.lnk')
        exit 1
    }
    Write-Host "round ${round}: Windows launched the link: $ok says '$((Get-Content -LiteralPath $ok -Raw).Trim())'"
}
Copy-Item -LiteralPath $lnk -Destination (Join-Path $env:CI_ART 'songcharter-test.lnk')
Write-Host '30-shortcut: ok'
