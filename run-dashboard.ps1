param([string]$Python = $env:DASHBOARD_PYTHON)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYTHONUTF8 = '1'
$dashboardCandidates = if ($Python) {
    @($Python)
} elseif ($env:CCTV_DASHBOARD_PYTHON) {
    @($env:CCTV_DASHBOARD_PYTHON)
} else {
    @((Join-Path $PSScriptRoot '.venv-cctv/Scripts/python.exe'),
      (Join-Path $PSScriptRoot '.venv/Scripts/python.exe'),
      (Join-Path $PSScriptRoot 'rr313/Scripts/python.exe'),
      (Join-Path $env:USERPROFILE 'venvs/rr313/Scripts/python.exe'),
      'python')
}
$dashboardPython = $null
foreach ($candidatePython in $dashboardCandidates) {
    $candidateExecutable = if (Test-Path -LiteralPath $candidatePython -PathType Leaf) {
        (Resolve-Path -LiteralPath $candidatePython).Path
    } else {
        (Get-Command -Name $candidatePython -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    }
    if (-not $candidateExecutable) { continue }
    try {
        & $candidateExecutable -B -c 'import streamlit' *> $null
        if ($LASTEXITCODE -eq 0) { $dashboardPython = $candidateExecutable; break }
    } catch { continue }
}
if (-not $dashboardPython) {
    throw 'Set CCTV_DASHBOARD_PYTHON to an existing Python environment with requirements-dashboard.txt installed.'
}
& $dashboardPython -m streamlit run busan_restroom_dashboard/app.py --server.address localhost --server.port 8501 --server.headless true --server.fileWatcherType poll --server.runOnSave true --server.maxUploadSize 500 --browser.gatherUsageStats false --theme.base light --theme.primaryColor '#0867df' --theme.backgroundColor '#f1f6fa' --theme.secondaryBackgroundColor '#ffffff' --theme.textColor '#172431'
exit $LASTEXITCODE
