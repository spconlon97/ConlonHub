param(
    [string]$HostAddress = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

function Read-DpapiSecret {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Encrypted credential not found: $Path"
    }

    $encryptedValue = (Get-Content -LiteralPath $Path -Raw).Trim()
    $secureValue = ConvertTo-SecureString $encryptedValue
    return [Net.NetworkCredential]::new("", $secureValue).Password
}

$credentialPath = Join-Path $env:LOCALAPPDATA "ConlonHub\openai_api_key.dpapi"
$pythonPath = Join-Path $PSScriptRoot "..\.venv-windows\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "MARVIS Python environment not found: $pythonPath"
}

try {
    $env:OPENAI_API_KEY = Read-DpapiSecret -Path $credentialPath

    if (-not $env:OPENAI_API_KEY.StartsWith("sk-")) {
        throw "The encrypted OpenAI credential is invalid."
    }

    $arguments = @(
        "-m", "uvicorn", "app.main:app",
        "--host", $HostAddress,
        "--port", $Port.ToString()
    )

    if ($Reload) {
        $arguments += "--reload"
    }

    & $pythonPath @arguments
    exit $LASTEXITCODE
}
finally {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
}
