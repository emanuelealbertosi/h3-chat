# Developer/CI only. End users run install.bat.
. (Join-Path $PSScriptRoot 'bootstrap-python.ps1')
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'static\app.js'))) {
    Write-Host 'Build dai sorgenti: Node.js richiesto soltanto per compilare l’interfaccia.'
    Push-Location $taskRoot
    try { & npm.cmd ci; if ($LASTEXITCODE -ne 0) { throw 'npm ci non riuscito.' }; & npm.cmd run build; if ($LASTEXITCODE -ne 0) { throw 'Build non riuscita.' } } finally { Pop-Location }
}
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath (Join-Path $taskRoot 'H3-Chat.exe')) -or (Get-Item -LiteralPath (Join-Path $taskRoot 'scripts\Launcher.cs')).LastWriteTimeUtc -gt (Get-Item -LiteralPath (Join-Path $taskRoot 'H3-Chat.exe')).LastWriteTimeUtc) {
    & $taskCompiler /nologo /target:winexe /reference:System.Windows.Forms.dll "/out:$taskRoot\H3-Chat.exe" "$taskRoot\scripts\Launcher.cs"
    if ($LASTEXITCODE -ne 0) { throw 'Creazione launcher non riuscita.' }
}
Write-Host 'H3-Chat pronto. Apri H3-Chat.exe e scegli hardware e modelli dal setup.'
