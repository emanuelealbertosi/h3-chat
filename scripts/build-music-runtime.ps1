param(
 [string]$AudioSource='',
 [ValidateSet('cpu','cuda')][string]$Backend='cuda',
 [string]$CudaToolkit=$env:CUDA_PATH_V12_8
)
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $AudioSource) {
 $taskCommit='13c4192a28d6a212f075c4cbefc5e4983e6ed52a'
 $taskSources=Join-Path $taskRoot 'work\music-source'
 New-Item -ItemType Directory -Path $taskSources -Force | Out-Null
 $taskArchive=Join-Path $taskSources 'audio-source.zip'
 if (-not (Test-Path -LiteralPath $taskArchive)) { Invoke-WebRequest -UseBasicParsing -Uri ('https://codeload.github.com/0xShug0/audio.cpp/zip/'+$taskCommit) -OutFile $taskArchive }
 if ((Get-FileHash -LiteralPath $taskArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne '7bdd528f8f0ec176823fb478ee7f03dbb8fdbd628f63f669ff281fe100b5a2dd') { throw 'audio.cpp source checksum mismatch.' }
 $AudioSource=Join-Path $taskSources ('audio.cpp-'+$taskCommit)
 if (-not (Test-Path -LiteralPath $AudioSource)) { Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskSources }

}
$taskSource=[IO.Path]::GetFullPath($AudioSource)
$taskPatch=Join-Path $taskRoot 'native\music\h3-artifacts.patch'
# Absolute directory is restricted to the caller-selected source root; the checked-in patch uses fixed relative paths.
if (Select-String -LiteralPath (Join-Path $taskSource 'include\engine\models\yue2\types.h') -SimpleMatch 'std::string h3_artifact_dir;' -Quiet) {
 & git -C $taskRoot apply --ignore-space-change --unsafe-paths "--directory=$taskSource" --reverse --check $taskPatch
} else {
 & git -C $taskRoot apply --ignore-space-change --unsafe-paths "--directory=$taskSource" --check $taskPatch
 if ($LASTEXITCODE -eq 0) { & git -C $taskRoot apply --ignore-space-change --unsafe-paths "--directory=$taskSource" $taskPatch }
}
if ($LASTEXITCODE -ne 0) { throw 'Cannot apply or verify the H3 artifact patch.' }

$taskVsWhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$taskVs=& $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $taskVs) { throw 'Install MSVC Build Tools x64 to rebuild the music worker.' }
$taskVc=Join-Path $taskVs 'VC\Auxiliary\Build\vcvars64.bat'
$taskCmake=Join-Path $taskVs 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
$taskNinja=Join-Path $taskVs 'Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe'
$taskBuild=Join-Path $taskRoot ('work\music-build-'+$Backend)
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
$taskCuda=if($Backend -eq 'cuda') {'ON'}else{'OFF'}
$taskCompiler=''
if ($Backend -eq 'cuda') {
 if (-not $CudaToolkit) { $CudaToolkit=Join-Path $env:ProgramFiles 'NVIDIA GPU Computing Toolkit\CUDA\v12.8' }
 $taskNvcc=Join-Path $CudaToolkit 'bin\nvcc.exe'
 if (-not (Test-Path -LiteralPath $taskNvcc)) { throw 'CUDA Toolkit 12.8 or later is required; specify -CudaToolkit.' }
 $taskCompiler='-DCMAKE_CUDA_COMPILER="'+$taskNvcc+'"'
}
$taskBatch=Join-Path $taskBuild 'build.cmd'
@"
@echo off
call "$taskVc" >nul
if errorlevel 1 exit /b 1
"$taskCmake" -S "$taskRoot/native/music" -B "$taskBuild" -G Ninja $taskCompiler -DCMAKE_MAKE_PROGRAM="$taskNinja" -DCMAKE_BUILD_TYPE=Release -DAUDIOCPP_SOURCE_DIR="$taskSource" -DAUDIOCPP_MODEL_SET=custom -DAUDIOCPP_MODELS=yue2 -DENGINE_ENABLE_CUDA=$taskCuda -DENGINE_ENABLE_NATIVE_CPU=OFF -DENGINE_BUILD_TESTS=OFF "-DCMAKE_CUDA_ARCHITECTURES=75-virtual;120-real"
if errorlevel 1 exit /b 1
"$taskCmake" --build "$taskBuild" --target h3-music-worker --parallel 6
exit /b %errorlevel%
"@ | Set-Content -LiteralPath $taskBatch -Encoding ASCII
& $taskBatch
if ($LASTEXITCODE -ne 0) { throw 'Music worker compilation failed.' }
$taskOutput=Join-Path $taskRoot ('runtime\music\'+$Backend)
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $taskBuild 'h3-music-worker.exe') -Destination $taskOutput
Get-FileHash -LiteralPath (Join-Path $taskOutput 'h3-music-worker.exe') -Algorithm SHA256

# Private redistributables: no admin install and no DLL lookup in another app.
$taskRedist=Get-ChildItem -LiteralPath (Join-Path $taskVs 'VC\Redist\MSVC') -Directory | Where-Object {$_.Name -match '^14\.'} | Sort-Object Name -Descending | Select-Object -First 1
if (-not $taskRedist) { throw 'MSVC redistributable folder not found.' }
foreach ($taskDll in @('msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll')) {
 Copy-Item -LiteralPath (Join-Path $taskRedist.FullName ('x64\Microsoft.VC143.CRT\'+$taskDll)) -Destination $taskOutput
}
Copy-Item -LiteralPath (Join-Path $taskRedist.FullName 'x64\Microsoft.VC143.OpenMP\vcomp140.dll') -Destination $taskOutput
& python (Join-Path $taskRoot 'scripts\music-notices.py') --source $taskSource --output $taskOutput
if ($LASTEXITCODE -ne 0) { throw 'Music runtime notices failed.' }
