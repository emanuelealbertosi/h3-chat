# Clone installer: only precompiled, checksum-verified components.
param([switch]$ApiOnly)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'bootstrap-python.ps1')
$taskInstallArguments = @('-X', 'utf8', '-u', (Join-Path $PSScriptRoot 'install.py'))
if ($ApiOnly) { $taskInstallArguments += '--api-only' }
& (Join-Path $taskPythonDir 'python.exe') @taskInstallArguments
if ($LASTEXITCODE -ne 0) { throw 'Installazione incompleta. Correggi il problema indicato e rilancia install.bat.' }
