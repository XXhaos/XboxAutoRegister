# ================= CONFIG =================
$API_URL = "http://127.0.0.1:9090"
$SECRET  = "8130899"
$GROUP   = "Rotate"
# ==========================================

# 1. Force UTF-8 Output
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "1. Connecting to Clash..." -ForegroundColor Cyan

# Use WebClient (Stable & Fixes Encoding)
$wc = New-Object System.Net.WebClient
$wc.Encoding = [System.Text.Encoding]::UTF8

try {
    # URL
    $ListUrl = "$API_URL/proxies/$GROUP"
    
    # === Step A: Get List ===
    # Add Auth Header
    if ($SECRET -ne "") { $wc.Headers.Add("Authorization", "Bearer $SECRET") }
    
    $JsonContent = $wc.DownloadString($ListUrl)
    
    $JsonObj = $JsonContent | ConvertFrom-Json
    $NodeList = $JsonObj.all

    if (!$NodeList -or $NodeList.Count -eq 0) {
        throw "Error: Group [$GROUP] is empty!"
    }
    Write-Host "   > Found $($NodeList.Count) nodes." -ForegroundColor Green

    # === Step B: Pick Random ===
    $Target = $NodeList | Get-Random
    Write-Host "2. Switching to: $Target" -ForegroundColor Cyan

    # === Step C: Send Switch Command ===
    $Payload = @{ name = $Target } | ConvertTo-Json -Compress
    
    # 【Critical Fix】Clear headers to remove old Auth, preventing duplicate headers
    $wc.Headers.Clear()
    
    # Re-add Headers correctly
    $wc.Headers.Add("Content-Type", "application/json")
    if ($SECRET -ne "") { $wc.Headers.Add("Authorization", "Bearer $SECRET") }

    # Send PUT
    $Response = $wc.UploadString($ListUrl, "PUT", $Payload)

    Write-Host "3. [SUCCESS] Switched to: $Target" -ForegroundColor Green

} catch {
    Write-Host "==== ERROR ====" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Yellow
    if ($_.Exception.InnerException) {
         Write-Host "Detail: $($_.Exception.InnerException.Message)" -ForegroundColor Yellow
    }
    exit 1
}