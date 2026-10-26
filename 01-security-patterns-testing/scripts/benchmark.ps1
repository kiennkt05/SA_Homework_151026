param([int]$Requests = 10)

$ErrorActionPreference = 'Stop'
$gateway = 'http://localhost:8080'
$login = Invoke-RestMethod -Method Post -Uri "$gateway/login" -ContentType 'application/json' -Body '{"email":"admin@example.com","password":"admin123"}'
$gatewayHeaders = @{ Authorization = "Bearer $($login.token)" }
$directHeaders = @{ 'x-auth-user-id' = '1' }

function Measure-Endpoint([string]$Name, [string]$Uri, [hashtable]$Headers) {
  $samples = @()
  1..$Requests | ForEach-Object {
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    Invoke-WebRequest -Uri $Uri -Headers $Headers | Out-Null
    $watch.Stop()
    $samples += $watch.Elapsed.TotalMilliseconds
  }

  $sorted = $samples | Sort-Object
  $p95Index = [Math]::Min($sorted.Count - 1, [Math]::Ceiling($sorted.Count * 0.95) - 1)
  [PSCustomObject]@{
    Path = $Name
    Requests = $Requests
    AverageMs = [Math]::Round(($samples | Measure-Object -Average).Average, 2)
    P95Ms = [Math]::Round($sorted[$p95Index], 2)
    MinMs = [Math]::Round($sorted[0], 2)
    MaxMs = [Math]::Round($sorted[-1], 2)
  }
}

$direct = Measure-Endpoint 'Direct -> User service' 'http://localhost:3001/users/1' $directHeaders
Start-Sleep -Milliseconds 1100
$throughGateway = Measure-Endpoint 'Client -> Gateway -> User service' "$gateway/users/1" $gatewayHeaders

$direct, $throughGateway | Format-Table -AutoSize
$overhead = $throughGateway.AverageMs - $direct.AverageMs
Write-Host "Average gateway overhead: $([Math]::Round($overhead, 2)) ms"

