# Build Media Downloader for Windows.
# Produces dist\MediaDownloader.exe and, if Inno Setup is present,
# dist\MediaDownloader-Windows-Setup.exe
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Write-Host "==> Fetching ffmpeg"
& $python packaging\fetch_ffmpeg.py

Write-Host "==> Building exe"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
& $python -m PyInstaller --noconfirm --clean packaging\MediaDownloader.spec

$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    Write-Host "==> Building installer"
    & $iscc packaging\installer.iss
} else {
    Write-Warning "Inno Setup not found, skipping installer. Standalone exe is in dist\"
}

Write-Host "`n==> Done"
Get-ChildItem dist\*.exe | ForEach-Object {
    "    {0}  {1:N1} MB" -f $_.Name, ($_.Length / 1MB)
}
