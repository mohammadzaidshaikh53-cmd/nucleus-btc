param([Parameter(ValueFromRemainingArguments=$true)][string[]]$NucleusArguments)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python.ps1')
$taskProject = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $taskProject
try {
    & (Get-NucleusPython) -m nucleus_btc @NucleusArguments
    if ($LASTEXITCODE -ne 0) { throw "Nucleus command failed: $LASTEXITCODE" }
} finally { Pop-Location }
