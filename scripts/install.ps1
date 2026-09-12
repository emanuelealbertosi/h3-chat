$ErrorActionPreference = 'Stop'
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
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'static\app.js'))) {
    Write-Host 'Build dai sorgenti: Node.js richiesto soltanto per compilare l’interfaccia.'
    Push-Location $taskRoot
    try { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw 'npm ci non riuscito.' }; & npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Build non riuscita.' } } finally { Pop-Location }
}
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'H3-Chat.exe'))) {
    & $taskCompiler /nologo /target:winexe /reference:System.Windows.Forms.dll "/out:$taskRoot\H3-Chat.exe" "$taskRoot\scripts\Launcher.cs"
    if ($LASTEXITCODE -ne 0) { throw 'Creazione launcher non riuscita.' }
}
Write-Host 'H3-Chat pronto. Apri H3-Chat.exe e scegli hardware e modelli dal setup.'
