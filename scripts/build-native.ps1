$ErrorActionPreference = 'Stop'
$taskProject = Split-Path -Parent $PSScriptRoot
$taskVswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $taskVswhere)) { throw 'MSVC Build Tools were not found. Use CMake with a C++20 compiler instead.' }
$taskVsRoot = & $taskVswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $taskVsRoot) { throw 'Install the MSVC C++ Build Tools workload or use CMake with another compiler.' }
$taskVcvars = Join-Path $taskVsRoot 'VC\Auxiliary\Build\vcvars64.bat'
$taskBuild = Join-Path $taskProject 'build'
New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
Push-Location -LiteralPath $taskBuild
try {
    $taskCommand = 'call "' + $taskVcvars + '" >nul && cl /nologo /std:c++20 /O2 /EHsc /W4 /LD /I"' + $taskProject + '\native\include" "' + $taskProject + '\native\src\core.cpp" /link /OUT:nucleus_core.dll && cl /nologo /std:c++20 /O2 /EHsc /W4 /I"' + $taskProject + '\native\include" "' + $taskProject + '\native\src\main.cpp" /Fe:nucleus-native.exe'
    & $env:ComSpec /d /s /c $taskCommand
    if ($LASTEXITCODE -ne 0) { throw "Native compilation failed: $LASTEXITCODE" }
} finally { Pop-Location }
