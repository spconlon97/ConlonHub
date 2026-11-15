param(
    [switch]$List,
    [string]$Revoke
)

# Pair a phone browser with MARVIS, or list/revoke paired phones.
# Default: print a one-time 6-digit code (valid 5 minutes) to enter on /phone.

$ErrorActionPreference = "Stop"

$pythonCandidates = @(
    (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"),
    (Join-Path $PSScriptRoot "..\.venv-windows\Scripts\python.exe")
)
$pythonPath = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $pythonPath) {
    throw "MARVIS Python environment not found. Create .venv from the Setup instructions."
}

if ($List -and $Revoke) {
    throw "Use either -List or -Revoke, not both."
}

Push-Location (Join-Path $PSScriptRoot "..")
try {
    if ($List) {
        $output = & $pythonPath -m app.core.auth.phone_pairing --list
    } elseif ($Revoke) {
        $output = & $pythonPath -m app.core.auth.phone_pairing --revoke $Revoke
    } else {
        $output = & $pythonPath -m app.core.auth.phone_pairing --new
    }
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}

$result = $output | ConvertFrom-Json

if ($List) {
    if (-not $result.devices) {
        Write-Host "No phones are paired."
    } else {
        $result.devices | Format-Table device_id, name, created_at, revoked_at -AutoSize
    }
} elseif ($Revoke) {
    if ($result.revoked) {
        Write-Host "Phone $Revoke revoked." -ForegroundColor Green
    } else {
        Write-Host "No active phone with ID $Revoke." -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "  MARVIS pairing code: $($result.code)" -ForegroundColor Cyan
    Write-Host "  Enter it on your phone at /phone. It works once and expires $($result.expires_at)."
    Write-Host ""
}

exit $exitCode
