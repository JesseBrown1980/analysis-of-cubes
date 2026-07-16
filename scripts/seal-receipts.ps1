param(
  [switch]$Verify
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$rootPrefix = $root.TrimEnd('\') + '\'
$receiptFiles = Get-ChildItem -LiteralPath $root -Recurse -File |
  Where-Object {
    $_.FullName -notmatch '\\.git\\' -and
    $_.Extension -in '.hbp', '.hbi'
  } |
  Sort-Object FullName

if ($Verify) {
  $failures = @()
  foreach ($file in $receiptFiles) {
    $sidecar = "$($file.FullName).sha256"
    if (-not (Test-Path -LiteralPath $sidecar)) {
      $failures += "MISSING $sidecar"
      continue
    }
    $expected = ((Get-Content -LiteralPath $sidecar -Raw).Trim() -split '\s+')[0].ToUpperInvariant()
    $actual = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    if ($actual -ne $expected) {
      $failures += "MISMATCH $($file.FullName)"
    }
  }
  if ($failures.Count) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
  }
  Write-Output "RECEIPTS_VERIFIED|count=$($receiptFiles.Count)|status=PASS"
  exit 0
}

$sumRows = foreach ($file in $receiptFiles) {
  if (-not $file.FullName.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Receipt escaped repository root: $($file.FullName)"
  }
  $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  $relative = $file.FullName.Substring($rootPrefix.Length).Replace('\', '/')
  Set-Content -LiteralPath "$($file.FullName).sha256" -Value "$hash  $relative" -Encoding utf8
  "$hash  $relative"
}

Set-Content -LiteralPath (Join-Path $root 'SHA256SUMS') -Value $sumRows -Encoding utf8
$master = (Get-FileHash -LiteralPath (Join-Path $root 'SHA256SUMS') -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $root 'SHA256SUMS.sha256') -Value "$master  SHA256SUMS" -Encoding utf8
Write-Output "RECEIPTS_SEALED|count=$($receiptFiles.Count)|status=PASS"
