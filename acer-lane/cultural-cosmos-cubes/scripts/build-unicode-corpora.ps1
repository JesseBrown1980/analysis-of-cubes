[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$UnicodeData,
    [string]$Manifest,
    [string]$CorpusRoot
)

$ErrorActionPreference = 'Stop'
$scriptRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($scriptRoot)) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrWhiteSpace($Manifest)) {
    $Manifest = Join-Path $scriptRoot '..\manifests\CORPUS-SOURCES.hbp'
}
if ([string]::IsNullOrWhiteSpace($CorpusRoot)) {
    $CorpusRoot = Join-Path $scriptRoot '..\corpora'
}

function Parse-HbpRow {
    param([string]$Line)
    $parts = $Line -split '\|'
    $row = [ordered]@{ kind = $parts[0] }
    foreach ($part in $parts[1..($parts.Count - 1)]) {
        if ($part -notmatch '=') { continue }
        $pair = $part -split '=', 2
        $row[$pair[0]] = $pair[1]
    }
    [pscustomobject]$row
}

if (-not (Test-Path -LiteralPath $UnicodeData -PathType Leaf)) {
    throw "UnicodeData.txt not found: $UnicodeData"
}

$records = foreach ($line in Get-Content -LiteralPath $UnicodeData) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $fields = $line -split ';'
    [pscustomobject]@{
        Codepoint = [Convert]::ToInt32($fields[0], 16)
        Hex = $fields[0]
        Name = $fields[1]
        Category = $fields[2]
        Combining = $fields[3]
        Bidi = $fields[4]
        Decomposition = $fields[5]
        Numeric = $fields[8]
    }
}

$corpora = Get-Content -LiteralPath $Manifest |
    Where-Object { $_ -match '^CORPUS\|' } |
    ForEach-Object { Parse-HbpRow $_ }

foreach ($corpus in $corpora) {
    $selected = [System.Collections.Generic.List[object]]::new()
    foreach ($range in ($corpus.ranges -split ',')) {
        $bounds = $range -split '-', 2
        $lo = [Convert]::ToInt32($bounds[0], 16)
        $hi = [Convert]::ToInt32($bounds[1], 16)
        foreach ($record in $records) {
            if ($record.Codepoint -ge $lo -and $record.Codepoint -le $hi) {
                $selected.Add($record)
            }
        }
    }

    $sourceDir = Join-Path $CorpusRoot "$($corpus.id)\source"
    New-Item -ItemType Directory -Force -Path $sourceDir | Out-Null
    $outFile = Join-Path $sourceDir 'unicode-assigned-codepoints.tsv'
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add("codepoint`tname`tcategory`tcombining`tbidi`tdecomposition`tnumeric")
    foreach ($record in ($selected | Sort-Object Codepoint)) {
        $lines.Add("U+$($record.Hex)`t$($record.Name)`t$($record.Category)`t$($record.Combining)`t$($record.Bidi)`t$($record.Decomposition)`t$($record.Numeric)")
    }
    [System.IO.File]::WriteAllLines($outFile, $lines, [System.Text.UTF8Encoding]::new($false))

    $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $UnicodeData).Hash.ToLowerInvariant()
    $derivativeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $outFile).Hash.ToLowerInvariant()
    $receipt = @(
        "CORPUSHDR|schema=UCD_RANGE_TSV_V1|corpus=$($corpus.id)|source_id=$($corpus.source_id)|culture_id=$($corpus.culture_id)|script_id=$($corpus.script_id)|language_id=$($corpus.language_id)|json=0",
        "SOURCE|file=UnicodeData.txt|sha256=$sourceHash|ranges=$($corpus.ranges)|authority=Unicode_Consortium|json=0",
        "DERIVATIVE|file=unicode-assigned-codepoints.tsv|rows=$($selected.Count)|sha256=$derivativeHash|normalization=assigned_records_sorted_by_codepoint_utf8_lf|json=0",
        "BOUNDARY|inventory_only=1|historical_language_semantics_claimed=0|translation_claimed=0|claims_final_apex=0|json=0"
    )
    [System.IO.File]::WriteAllLines(
        (Join-Path $sourceDir 'CORPUS.hbp'),
        $receipt,
        [System.Text.UTF8Encoding]::new($false)
    )
    Write-Output "UNICODE_CORPUS_PASS|id=$($corpus.id)|rows=$($selected.Count)|sha256=$derivativeHash|json=0"
}
