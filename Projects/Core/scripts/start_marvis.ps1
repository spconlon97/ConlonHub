param(
    [string]$HostAddress = "127.0.0.1",
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [ValidateSet("ollama", "openai")]
    [string]$Provider = "ollama",
    [string]$Model,
    [string]$OllamaEndpoint = "http://127.0.0.1:11434/api/chat",
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
$pythonCandidates = @(
    (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"),
    (Join-Path $PSScriptRoot "..\.venv-windows\Scripts\python.exe")
)
$pythonPath = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $pythonPath) {
    throw "MARVIS Python environment not found. Create .venv from the Setup instructions."
}

try {
    $env:AI_PROVIDER = $Provider

    if ($Provider -eq "ollama") {
        $env:OLLAMA_MODEL = if ([string]::IsNullOrWhiteSpace($Model)) {
            "qwen3.5:9b"
        } else {
            $Model.Trim()
        }
        $env:OLLAMA_ENDPOINT = $OllamaEndpoint
    }
    else {
        $env:OPENAI_API_KEY = Read-DpapiSecret -Path $credentialPath

        if (-not $env:OPENAI_API_KEY.StartsWith("sk-")) {
            throw "The encrypted OpenAI credential is invalid."
        }

        if (-not [string]::IsNullOrWhiteSpace($Model)) {
            $env:OPENAI_MODEL = $Model.Trim()
        }
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
    Remove-Item Env:AI_PROVIDER, Env:OLLAMA_MODEL, Env:OLLAMA_ENDPOINT, `
        Env:OPENAI_API_KEY, Env:OPENAI_MODEL -ErrorAction SilentlyContinue
}
