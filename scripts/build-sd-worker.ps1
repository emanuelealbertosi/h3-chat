$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskVsWhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$taskVs = & $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $taskVs) { throw 'MSVC Build Tools x64 required to rebuild the native worker.' }
$taskVc = Join-Path $taskVs 'VC\Auxiliary\Build\vcvars64.bat'
$taskBuild = Join-Path $taskRoot 'work\native-build'
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
$taskSource = Join-Path $taskRoot 'native\sd-worker.cpp'
$taskExe = Join-Path $taskRoot 'native\h3-sd-worker.exe'
$taskObj = Join-Path $taskBuild 'sd-worker.obj'
$taskBatch = Join-Path $taskBuild 'compile.cmd'
@"
@echo off
call "$taskVc" >nul
if errorlevel 1 exit /b 1
cl.exe /nologo /std:c++17 /EHsc /O2 /MT /utf-8 /DNDEBUG /Fo"$taskObj" /Fe"$taskExe" "$taskSource" /link /INCREMENTAL:NO
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $taskBatch -Encoding ASCII
& $taskBatch
if ($LASTEXITCODE -ne 0) { throw 'Native worker build failed.' }
Get-FileHash -LiteralPath $taskExe -Algorithm SHA256
