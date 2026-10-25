param([string]$Python = $env:DASHBOARD_PYTHON)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $Python) {
    foreach ($candidate in @('.venv-cctv\Scripts\python.exe', '.venv\Scripts\python.exe', 'rr313\Scripts\python.exe')) {
        if (Test-Path -LiteralPath $candidate) {
            $Python = (Resolve-Path -LiteralPath $candidate).Path
            break
        }
    }
}
if (-not $Python) { $Python = 'python' }
$env:PYTHONUTF8 = '1'
& $Python -m streamlit run busan_restroom_dashboard/app.py --server.address localhost --server.port 8501 --server.headless true --server.maxUploadSize 500 --browser.gatherUsageStats false --theme.base light --theme.primaryColor '#0867df' --theme.backgroundColor '#f1f6fa' --theme.secondaryBackgroundColor '#ffffff' --theme.textColor '#172431'
exit $LASTEXITCODE
