# Download a Windows ffmpeg into studio\tools\ffmpeg\bin.
# install.bat calls this. You do not run it yourself.
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"

$studio = Split-Path -Parent $PSScriptRoot
$bin = Join-Path $studio "tools\ffmpeg\bin"
$exe = Join-Path $bin "ffmpeg.exe"
if (Test-Path $exe) {
  Write-Host "ffmpeg is already here."
  exit 0
}

Write-Host "Downloading ffmpeg. This can take a few minutes."
$zip = Join-Path $env:TEMP "mowstudio-ffmpeg.zip"
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
Invoke-WebRequest -Uri $url -OutFile $zip

$unpack = Join-Path $studio "tools\_ffmpeg"
if (Test-Path $unpack) { Remove-Item -Recurse -Force $unpack }
New-Item -ItemType Directory -Force -Path $unpack | Out-Null
Expand-Archive -Path $zip -DestinationPath $unpack -Force

$inner = Get-ChildItem -Path $unpack -Directory | Select-Object -First 1
if (-not $inner) { throw "The ffmpeg download did not look right." }
New-Item -ItemType Directory -Force -Path $bin | Out-Null
Copy-Item -Path (Join-Path $inner.FullName "bin\*") -Destination $bin -Force
if (-not (Test-Path $exe)) { throw "ffmpeg.exe was not found after unzip." }
Write-Host "ffmpeg is ready."
