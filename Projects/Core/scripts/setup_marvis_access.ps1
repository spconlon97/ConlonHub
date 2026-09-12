param(
    [string]$Name = "MARVIS Owner"
)

$ErrorActionPreference = "Stop"

$pythonCandidates = @(
    (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"),
    (Join-Path $PSScriptRoot "..\.venv-windows\Scripts\python.exe")
)
$pythonPath = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $pythonPath) {
    throw "MARVIS Python environment not found. Create .venv from the Setup instructions."
}

$secureFolder = Join-Path $env:LOCALAPPDATA "ConlonHub"
$secureFile = Join-Path $secureFolder "marvis_api_key.dpapi"

if (Test-Path -LiteralPath $secureFile) {
    Write-Host "MARVIS private local access is already ready." -ForegroundColor Green
    Write-Host $secureFile
    return
}

$bootstrapOutput = $null
$payload = $null
$apiKey = $null
$secureValue = $null
$encryptedValue = $null
$savedEncryptedValue = $null
$savedValue = $null
$verifiedKey = $null

try {
    $bootstrapOutput = & $pythonPath -m app.core.auth.bootstrap --name $Name
    if ($LASTEXITCODE -ne 0) {
        throw "MARVIS access credential generation failed."
    }

    $payload = $bootstrapOutput | ConvertFrom-Json
    $apiKey = [string]$payload.api_key
    if ($apiKey -notmatch '^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$') {
        throw "MARVIS returned an invalid access credential."
    }

    New-Item -ItemType Directory -Path $secureFolder -Force | Out-Null
    $secureValue = ConvertTo-SecureString $apiKey -AsPlainText -Force
    $encryptedValue = ConvertFrom-SecureString $secureValue
    Set-Content -LiteralPath $secureFile -Value $encryptedValue

    $savedEncryptedValue = (Get-Content -LiteralPath $secureFile -Raw).Trim()
    $savedValue = ConvertTo-SecureString $savedEncryptedValue
    $verifiedKey = [Net.NetworkCredential]::new("", $savedValue).Password
    if ($verifiedKey -ne $apiKey) {
        throw "Saved MARVIS access credential verification failed."
    }

    Write-Host "MARVIS private local access is ready." -ForegroundColor Green
    Write-Host $secureFile
}
finally {
    Remove-Variable bootstrapOutput, payload, apiKey, secureValue, encryptedValue, `
        savedEncryptedValue, savedValue, verifiedKey -ErrorAction SilentlyContinue
}
