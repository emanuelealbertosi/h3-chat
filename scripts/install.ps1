# Clone installer: only precompiled, checksum-verified components.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bootstrap-python.ps1')
& (Join-Path $taskPythonDir 'python.exe') -X utf8 -u (Join-Path $PSScriptRoot 'install.py')
if ($LASTEXITCODE -ne 0) { throw 'Installazione incompleta. Correggi il problema indicato e rilancia install.bat.' }
