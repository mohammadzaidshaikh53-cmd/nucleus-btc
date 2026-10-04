param([switch]$SkipOptimization)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\python.ps1')
$taskPython = Get-NucleusPython
Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath 'build\nucleus_core.dll')) { & '.\scripts\build-native.ps1' }
    & '.\scripts\test.ps1'
    $taskCommands = @(
        @('doctor'),
        @('verify','--backend','opencl','--samples','16384','--output','results\verification.json'),
        @('benchmark','--output','results\gpu-baseline.json')
    )
    if (-not $SkipOptimization) { $taskCommands += ,@('optimize','--output','results\optimizer.json') }
    $taskCommands += ,@('benchmark','--champion','--output','results\gpu-champion.json')
    $taskCommands += ,@('confirm','--output','results\confirmation.json')
    $taskCommands += ,@('scaling','--champion','--output','results\family-scaling.json')
    $taskCommands += ,@('research','--representation','dag','--output','results\symbolic-dag.json')
    $taskCommands += ,@('research','--representation','bdd','--max-nodes','100000','--output','results\symbolic-bdd.json')
    $taskCommands += ,@('portfolio','--output','results\research-portfolio.json')
    $taskCommands += ,@('scan','--champion','--output','results\genesis-scan.json')
    foreach ($taskArguments in $taskCommands) {
        & $taskPython -m nucleus_btc @taskArguments
        if ($LASTEXITCODE -ne 0) { throw "Stage failed: $($taskArguments[0])" }
    }
    Write-Host 'Local stages completed. Review results and config/pool.example.json before a live pool run.'
} finally { Pop-Location }
