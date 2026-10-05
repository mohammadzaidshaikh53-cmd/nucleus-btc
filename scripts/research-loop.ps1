param([int]$Steps = 16, [int]$Seconds = 3600, [switch]$Forever)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python.ps1')
Push-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
try {
    $arguments = @('-m', 'nucleus_btc', 'evolve', '--steps', $Steps, '--seconds', $Seconds)
    if ($Forever) { $arguments += '--forever' }
    & (Get-NucleusPython) @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Supervisor failed; durable checkpoint retained.' }
} finally { Pop-Location }
