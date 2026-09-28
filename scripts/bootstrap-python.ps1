$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$env:PYTHONUTF8 = '1'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskPythonDir = Join-Path $taskRoot 'runtime\python'
$taskArchive = Join-Path $taskRoot 'runtime\python-3.13.15-embed-amd64.zip'
$taskExpected = 'd1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf'
if (-not (Test-Path -LiteralPath (Join-Path $taskPythonDir 'python.exe'))) {
    New-Item -ItemType Directory -Force -Path $taskPythonDir | Out-Null
    Write-Host 'Preparazione del runtime Python integrato...'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.13.15/python-3.13.15-embed-amd64.zip' -OutFile $taskArchive
    if ((Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskExpected) { throw 'Checksum Python non valido.' }
    Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskPythonDir -Force
}
# Isolated Python searches only its runtime and this application, never system site-packages.
@'
python313.zip
.
..\..
'@ | Set-Content -LiteralPath (Join-Path $taskPythonDir 'python313._pth') -Encoding ASCII
