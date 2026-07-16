[CmdletBinding()]
param(
    [string]$CorpusRoot,
    [string]$ResultRoot,
    [string]$Trainer,
    [string]$Seat = 'ACER',
    [string[]]$CorpusId,
    [ValidateSet('Auto', 'GNU', 'MSVC')]
    [string]$RustToolchain = 'Auto'
)

$ErrorActionPreference = 'Stop'
$scriptRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($scriptRoot)) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrWhiteSpace($CorpusRoot)) {
    $CorpusRoot = Join-Path $scriptRoot '..\corpora'
}
if ([string]::IsNullOrWhiteSpace($ResultRoot)) {
    $ResultRoot = Join-Path $scriptRoot '..\results'
}
if ([string]::IsNullOrWhiteSpace($Trainer)) {
    $Trainer = Join-Path $scriptRoot '..\..\trained-cubes\unified-omega\unified_omega.rs'
}

function Select-RustCompiler {
    param(
        [Parameter(Mandatory)]
        [string]$Preference
    )
    $rustup = Get-Command rustup -ErrorAction SilentlyContinue
    if ($rustup) {
        $installed = @(& $rustup.Source toolchain list) |
            ForEach-Object { ($_ -split '\s+')[0] } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        $gnu = $installed | Where-Object { $_ -match '-pc-windows-gnu$' } | Select-Object -First 1
        $msvc = $installed | Where-Object { $_ -match '-pc-windows-msvc$' } | Select-Object -First 1
        $selected = switch ($Preference) {
            'GNU' {
                if (-not $gnu) { throw 'Requested GNU Rust toolchain is not installed.' }
                $gnu
            }
            'MSVC' {
                if (-not $msvc) { throw 'Requested MSVC Rust toolchain is not installed.' }
                $msvc
            }
            default {
                if ($gnu) { $gnu }
                elseif ($msvc) { $msvc }
                else { $null }
            }
        }
        if ($selected) {
            return [pscustomobject]@{
                Command = $rustup.Source
                Prefix = @('run', $selected, 'rustc')
                Label = $selected
            }
        }
    }
    if ($Preference -ne 'Auto') {
        throw "Rust toolchain selection $Preference requires rustup with the requested target installed."
    }
    $rustc = Get-Command rustc -ErrorAction Stop
    return [pscustomobject]@{
        Command = $rustc.Source
        Prefix = @()
        Label = 'default-rustc'
    }
}

if (-not (Test-Path -LiteralPath $Trainer -PathType Leaf)) {
    throw "Trainer not found: $Trainer"
}

$binDir = Join-Path $ResultRoot '.bin'
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
$trainerExe = Join-Path $binDir 'unified_omega.exe'
$compiler = Select-RustCompiler -Preference $RustToolchain
$rustArgs = @($compiler.Prefix) + @('--edition=2021', '-O', $Trainer, '-o', $trainerExe)

& $compiler.Command @rustArgs
if ($LASTEXITCODE -ne 0) { throw "rustc failed with exit code $LASTEXITCODE using $($compiler.Label)" }

& $trainerExe selftest
if ($LASTEXITCODE -ne 0) { throw "trainer selftest failed with exit code $LASTEXITCODE" }

$corpusDirs = @(
    Get-ChildItem -LiteralPath $CorpusRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object {
            (-not $CorpusId -or $_.Name -in $CorpusId) -and
            (Test-Path -LiteralPath (Join-Path $_.FullName 'source') -PathType Container)
        } |
        Sort-Object Name
)

if ($corpusDirs.Count -eq 0) {
    throw "No corpus source directories found under $CorpusRoot"
}

$indexRows = [System.Collections.Generic.List[string]]::new()
$indexRows.Add("BATCHHDR|schema=ASOLARIA-CULTURAL-COSMOS-BATCH-V1|seat=$Seat|corpora=$($corpusDirs.Count)|rust_toolchain=$($compiler.Label)|claims_final_apex=0|json=0")

foreach ($corpus in $corpusDirs) {
    $sourceDir = Join-Path $corpus.FullName 'source'
    $outputDir = Join-Path $ResultRoot $corpus.Name
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

    & $trainerExe build --source $sourceDir --output $outputDir --seat $Seat
    if ($LASTEXITCODE -ne 0) {
        throw "Training failed for $($corpus.Name) with exit code $LASTEXITCODE"
    }

    $hbp = Join-Path $outputDir 'UNIFIED-OMEGA-RESULT.hbp'
    if (-not (Test-Path -LiteralPath $hbp -PathType Leaf)) {
        throw "Missing result for $($corpus.Name): $hbp"
    }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $hbp).Hash.ToLowerInvariant()
    $omegaLine = Get-Content -LiteralPath $hbp | Where-Object { $_ -match '^UNIFIEDOMEGA\|' } | Select-Object -First 1
    $omega = if ($omegaLine -match 'omega_unified=([0-9a-f]{64})') { $Matches[1] } else { 'MISSING' }
    $indexRows.Add("CORPUSRESULT|id=$($corpus.Name)|result_sha256=$hash|omega_unified=$omega|families=3|bodies=40|cells=60800|claims_final_apex=0|json=0")
}

$indexRows.Add("BATCHFTR|status=PASS|corpora=$($corpusDirs.Count)|live_promotion=GATED|paid_cloud_calls=0|claims_final_apex=0|json=0")
$indexPath = Join-Path $ResultRoot 'BATCH-INDEX.hbp'
[System.IO.File]::WriteAllLines($indexPath, $indexRows, [System.Text.UTF8Encoding]::new($false))
$indexHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $indexPath).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText(
    "$indexPath.sha256",
    "$indexHash  BATCH-INDEX.hbp`n",
    [System.Text.UTF8Encoding]::new($false)
)
Write-Output "CULTURAL_COSMOS_BATCH_PASS|corpora=$($corpusDirs.Count)|rust_toolchain=$($compiler.Label)|index_sha256=$indexHash|json=0"
