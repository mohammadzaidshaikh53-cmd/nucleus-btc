function Get-NucleusPython {
    $taskRuntime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $taskRuntime) { return $taskRuntime }
    $taskPython = Get-Command python -ErrorAction SilentlyContinue
    if ($taskPython) { return $taskPython.Source }
    throw 'Python 3.11 or newer is required.'
}
