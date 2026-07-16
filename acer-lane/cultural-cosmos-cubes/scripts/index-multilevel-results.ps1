[CmdletBinding()]
param(
    [string]$ResultRoot,
    [string]$Output
)

$ErrorActionPreference = 'Stop'
$scriptRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ResultRoot)) {
    $ResultRoot = Join-Path $scriptRoot '..\results'
}
if ([string]::IsNullOrWhiteSpace($Output)) {
    $Output = Join-Path $ResultRoot 'MULTILEVEL-BATCH-INDEX.hbp'
}

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$rows = [System.Collections.Generic.List[string]]::new()
$directories = @(
    Get-ChildItem -LiteralPath $ResultRoot -Directory |
        Where-Object { $_.Name -like '*-multilevel' } |
        Sort-Object Name
)

$passed = 0
$failed = 0
$rows.Add("MLBATCHHDR|schema=ASOLARIA-MULTILEVEL-BATCH-INDEX-V1|directories=$($directories.Count)|levels=64,256,1024,4096|claims_final_apex=0|json=0")

foreach ($directory in $directories) {
    $hbp = Join-Path $directory.FullName 'MULTILEVEL-QUANT-RESULT.hbp'
    $hbi = Join-Path $directory.FullName 'MULTILEVEL-QUANT-RESULT.hbi'
    $sum = Join-Path $directory.FullName 'SHA256SUMS.multilevel'
    $required = @($hbp, "$hbp.sha256", $hbi, "$hbi.sha256", $sum, "$sum.sha256")
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($missing.Count) {
        $failed += 1
        $rows.Add("MLRESULT|id=$($directory.Name)|status=FAIL_MISSING|missing=$($missing.Count)|json=0")
        continue
    }

    $hashFailures = 0
    foreach ($payload in @($hbp, $hbi, $sum)) {
        $expected = ([System.IO.File]::ReadAllText("$payload.sha256").Trim() -split '\s+')[0].ToLowerInvariant()
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $payload).Hash.ToLowerInvariant()
        if ($expected -ne $actual) { $hashFailures += 1 }
    }
    if ($hashFailures) {
        $failed += 1
        $rows.Add("MLRESULT|id=$($directory.Name)|status=FAIL_HASH|failures=$hashFailures|json=0")
        continue
    }

    $omegaRow = Get-Content -LiteralPath $hbp |
        Where-Object { $_ -match '^MLOMEGA\|' } |
        Select-Object -First 1
    if ($omegaRow -notmatch 'bodies=40\|level_states=160\|distinct_languages=160\|omega_unified=([0-9a-f]{64})\|source_restore=1') {
        $failed += 1
        $rows.Add("MLRESULT|id=$($directory.Name)|status=FAIL_CONTRACT|json=0")
        continue
    }
    $omega = $Matches[1]
    $sourceRow = Get-Content -LiteralPath $hbp |
        Where-Object { $_ -match '^MLHDR\|' } |
        Select-Object -First 1
    $sourceSha = if ($sourceRow -match 'source_sha256=([0-9a-f]{64})') { $Matches[1] } else { 'MISSING' }
    $resultSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $hbp).Hash.ToLowerInvariant()
    $passed += 1
    $rows.Add("MLRESULT|id=$($directory.Name)|status=PASS|source_sha256=$sourceSha|result_sha256=$resultSha|omega_unified=$omega|families=3|bodies=40|level_states=160|distinct_languages=160|json=0")
}

$status = if ($failed -eq 0) { 'PASS' } else { 'FAIL' }
$rows.Add("MLBATCHFTR|status=$status|passed=$passed|failed=$failed|compression_claim=0|physical_quantum_projection=UNVERIFIED|claims_final_apex=0|json=0")
[System.IO.File]::WriteAllText($Output, ($rows -join "`n") + "`n", $utf8NoBom)
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Output).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText("$Output.sha256", "$hash  $([System.IO.Path]::GetFileName($Output))`n", $utf8NoBom)
Write-Output "MULTILEVEL_BATCH_INDEX|status=$status|passed=$passed|failed=$failed|sha256=$hash|json=0"
if ($failed) { exit 1 }
