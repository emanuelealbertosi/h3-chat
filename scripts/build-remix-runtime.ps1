param([ValidateSet('cpu','cuda')][string]$Backend='cpu',[string]$AudioSource='')
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $AudioSource) {
 $AudioSource=Join-Path $taskRoot 'work\music-source\audio.cpp-13c4192a28d6a212f075c4cbefc5e4983e6ed52a'
 if (-not (Test-Path -LiteralPath $AudioSource)) { throw 'Run scripts/build-music-runtime.ps1 first to obtain the pinned audio.cpp source and artifact patch.' }
}
$taskSource=[IO.Path]::GetFullPath($AudioSource)
$taskVsWhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$taskVs=& $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $taskVs) { throw 'MSVC C++ Build Tools are required only to rebuild the native engine.' }
$taskVc=Join-Path $taskVs 'VC\Auxiliary\Build\vcvars64.bat'
$taskCmake=Join-Path $taskVs 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$taskNinja=Join-Path $taskVs 'Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe'
$taskBuild=Join-Path $taskRoot ('work\remix-build-'+$Backend)
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
$taskCuda=if($Backend -eq 'cuda') {'ON'}else{'OFF'}
$taskCompiler=if($Backend -eq 'cuda') {'-DCMAKE_CUDA_COMPILER="'+(Join-Path $env:CUDA_PATH_V12_8 'bin\nvcc.exe')+'"'}else{''}
$taskBatch=Join-Path $taskBuild 'build.cmd'
@"
@echo off
call "$taskVc" >nul
if errorlevel 1 exit /b 1
"$taskCmake" -S "$taskSource" -B "$taskBuild" -G Ninja $taskCompiler -DCMAKE_MAKE_PROGRAM="$taskNinja" -DCMAKE_BUILD_TYPE=Release -DAUDIOCPP_MODEL_SET=custom -DAUDIOCPP_MODELS="yue2;htdemucs;seed_vc" -DENGINE_ENABLE_CUDA=$taskCuda -DENGINE_ENABLE_NATIVE_CPU=OFF -DENGINE_BUILD_TESTS=OFF "-DCMAKE_CUDA_ARCHITECTURES=75-virtual;120-real"
if errorlevel 1 exit /b 1
"$taskCmake" --build "$taskBuild" --target audiocpp_cli --parallel 6
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $taskBatch -Encoding ASCII
& $taskBatch
if ($LASTEXITCODE -ne 0) { throw 'Remix engine build failed.' }
$taskOut=Join-Path $taskRoot ('runtime\remix\'+$Backend)
New-Item -ItemType Directory -Path $taskOut -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $taskBuild 'bin\audiocpp_cli.exe') -Destination $taskOut
Copy-Item -Path (Join-Path $taskRoot ('runtime\music\'+$Backend+'\*140*.dll')) -Destination $taskOut
& python (Join-Path $taskRoot 'scripts\music-notices.py') --source $taskSource --output $taskOut
if ($LASTEXITCODE -ne 0) { throw 'Cannot preserve native engine notices.' }
