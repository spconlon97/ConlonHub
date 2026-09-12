param(
    [string]$Prompt,
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function ConvertFrom-Utf8JsonResponse {
    param([Parameter(Mandatory)]$Response)

    if ($Response.RawContentStream) {
        $bytes = $Response.RawContentStream.ToArray()
        return [Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json
    }

    return $Response.Content | ConvertFrom-Json
}

function Read-DpapiSecret {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Encrypted credential not found: $Path"
    }

    $encryptedValue = (Get-Content -LiteralPath $Path -Raw).Trim()
    $secureValue = ConvertTo-SecureString $encryptedValue
    return [Net.NetworkCredential]::new("", $secureValue).Password
}

$credentialPath = Join-Path $env:LOCALAPPDATA "ConlonHub\marvis_api_key.dpapi"
$bearerToken = Read-DpapiSecret -Path $credentialPath
$headers = @{ Authorization = "Bearer $bearerToken" }
$conversationId = $null
$singlePrompt = -not [string]::IsNullOrWhiteSpace($Prompt)

try {
    $statusResponse = Invoke-WebRequest `
        -UseBasicParsing `
        -Uri "$BaseUrl/ai/status" `
        -Method Get `
        -TimeoutSec 10
    $status = ConvertFrom-Utf8JsonResponse $statusResponse
    Write-Host "MARVIS is $($status.status) using $($status.model)." -ForegroundColor Green

    while ($true) {
        if ($singlePrompt) {
            $userPrompt = $Prompt
        }
        else {
            $userPrompt = Read-Host "You"
        }

        if ([string]::IsNullOrWhiteSpace($userPrompt)) {
            if ($singlePrompt) { break }
            continue
        }

        if ($userPrompt.Trim() -in @("exit", "quit", "/exit")) {
            break
        }

        $requestBody = @{ prompt = $userPrompt.Trim() }
        if ($conversationId) {
            $requestBody.conversation_id = $conversationId
        }

        $webResponse = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "$BaseUrl/ai/respond" `
            -Method Post `
            -Headers $headers `
            -ContentType "application/json" `
            -Body ($requestBody | ConvertTo-Json) `
            -TimeoutSec 120
        $response = ConvertFrom-Utf8JsonResponse $webResponse

        $conversationId = $response.conversation_id
        Write-Host "MARVIS: $($response.response)" -ForegroundColor Cyan

        if ($singlePrompt) {
            break
        }
    }
}
catch {
    if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 404) {
        throw "MARVIS endpoint was not found at $BaseUrl."
    }
    if ($_.Exception.Message -match "refused|connect") {
        throw "MARVIS is not running. Start it with .\scripts\start_marvis.ps1 first."
    }
    throw
}
finally {
    Remove-Variable bearerToken, headers -ErrorAction SilentlyContinue
}
