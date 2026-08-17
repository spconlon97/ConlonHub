$ErrorActionPreference = "Stop"

$openAIKey = ([string](Get-Clipboard -Raw)).Trim()

if (-not $openAIKey.StartsWith("sk-")) {
    throw "The clipboard does not contain an OpenAI API key. Copy the secret key and try again."
}

$secureFolder = Join-Path $env:LOCALAPPDATA "ConlonHub"
$secureFile = Join-Path $secureFolder "openai_api_key.dpapi"

New-Item -ItemType Directory -Path $secureFolder -Force | Out-Null

$secureValue = ConvertTo-SecureString $openAIKey -AsPlainText -Force
$encryptedValue = ConvertFrom-SecureString $secureValue
$verifiedKey = [Net.NetworkCredential]::new(
    "",
    (ConvertTo-SecureString $encryptedValue)
).Password

if ($verifiedKey -ne $openAIKey) {
    throw "Encrypted-key verification failed. Nothing was saved."
}

Set-Content -LiteralPath $secureFile -Value $encryptedValue

$savedEncryptedValue = (Get-Content -LiteralPath $secureFile -Raw).Trim()
$savedValue = ConvertTo-SecureString $savedEncryptedValue
$savedKey = [Net.NetworkCredential]::new("", $savedValue).Password

if ($savedKey -ne $openAIKey) {
    throw "Saved-key verification failed."
}

Set-Clipboard -Value "cleared"
Remove-Variable openAIKey, secureValue, encryptedValue, verifiedKey, savedEncryptedValue, savedValue, savedKey `
    -ErrorAction SilentlyContinue

Write-Host "REAL SUCCESS: OpenAI key encrypted and verified."
Write-Host $secureFile
