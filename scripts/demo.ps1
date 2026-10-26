$ErrorActionPreference = 'Stop'
$gateway = 'http://localhost:8080'

$login = Invoke-RestMethod -Method Post -Uri "$gateway/login" -ContentType 'application/json' -Body (@{
  email = 'admin@example.com'
  password = 'admin123'
} | ConvertTo-Json)

$headers = @{ Authorization = "Bearer $($login.token)" }
Write-Host "JWT received (expires in $($login.expiresInSeconds) seconds)."

Write-Host "`nRouting /users:"
Invoke-RestMethod -Uri "$gateway/users/1" -Headers $headers | ConvertTo-Json

Write-Host "`nRouting /orders:"
Invoke-RestMethod -Uri "$gateway/orders?userId=1" -Headers $headers | ConvertTo-Json

Write-Host "`nAggregation /dashboard:"
Invoke-RestMethod -Uri "$gateway/dashboard?userId=1" -Headers $headers | ConvertTo-Json -Depth 5

Write-Host "`nValet Key (pre-signed URL valid for five minutes):"
$presigned = Invoke-RestMethod -Method Post -Uri "$gateway/users/1/avatar-upload-url" -Headers $headers -ContentType 'application/json' -Body '{"contentType":"image/png"}'
$temporaryAvatar = [System.IO.Path]::GetTempFileName()
try {
  [System.IO.File]::WriteAllBytes($temporaryAvatar, [byte[]](137,80,78,71,13,10,26,10))
  Invoke-WebRequest -Method Put -Uri $presigned.uploadUrl -ContentType 'image/png' -InFile $temporaryAvatar | Out-Null
  Write-Host "Uploaded directly to MinIO object: $($presigned.objectKey)"
} finally {
  Remove-Item -LiteralPath $temporaryAvatar -Force
}

Write-Host "`nRate limit (expect HTTP 429 after ten fast requests):"
Start-Sleep -Milliseconds 1100
1..12 | ForEach-Object {
  try {
    $response = Invoke-WebRequest -Uri "$gateway/users/1" -Headers $headers
    Write-Host "Request $_ -> $($response.StatusCode)"
  } catch {
    Write-Host "Request $_ -> $([int]$_.Exception.Response.StatusCode)"
  }
}

