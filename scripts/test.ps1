$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python.ps1')
Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    & (Get-NucleusPython) 'scripts\test_runner.py'
    if ($LASTEXITCODE -ne 0) { throw 'Verification suite failed.' }
} finally { Pop-Location }
