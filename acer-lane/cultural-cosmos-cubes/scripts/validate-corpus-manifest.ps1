[CmdletBinding()]
param(
    [string]$Manifest
)

$ErrorActionPreference = 'Stop'
$scriptRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($scriptRoot)) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrWhiteSpace($Manifest)) {
    $Manifest = Join-Path $scriptRoot '..\manifests\CORPUS-SOURCES.hbp'
}
$allowedStates = @(
    'MEASURED_PUBLISHED',
    'MEASURED_REPRODUCED',
    'MODEL_RECONSTRUCTION',
    'INTERPRETIVE_HYPOTHESIS',
    'OPERATOR_OBSERVED_UNDOCUMENTED',
    'KNOWN_CAPTURE_NOT_OPENLY_ACQUIRED',
    'PLANNED_DOWNLOAD',
    'UNVERIFIED'
)

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

if (-not (Test-Path -LiteralPath $Manifest -PathType Leaf)) {
    throw "Manifest not found: $Manifest"
}

$rows = Get-Content -LiteralPath $Manifest |
    Where-Object { $_ -match '^(SOURCE|CORPUS)\|' } |
    ForEach-Object { Parse-HbpRow $_ }

$sources = @($rows | Where-Object kind -eq 'SOURCE')
$corpora = @($rows | Where-Object kind -eq 'CORPUS')
$errors = [System.Collections.Generic.List[string]]::new()

$requiredSource = @(
    'id', 'category', 'authority', 'accession_or_doi', 'license',
    'source_uri', 'raw_sha256', 'derivative_sha256', 'state',
    'sensitivity', 'query', 'normalization'
)

foreach ($source in $sources) {
    foreach ($field in $requiredSource) {
        if (-not $source.PSObject.Properties.Name.Contains($field) -or
            [string]::IsNullOrWhiteSpace($source.$field)) {
            $errors.Add("SOURCE $($source.id) missing $field")
        }
    }
    if ($source.state -notin $allowedStates) {
        $errors.Add("SOURCE $($source.id) has invalid state $($source.state)")
    }
}

$duplicateSources = $sources | Group-Object id | Where-Object Count -gt 1
foreach ($duplicate in $duplicateSources) {
    $errors.Add("Duplicate SOURCE id $($duplicate.Name)")
}

$sourceIds = @{}
foreach ($source in $sources) { $sourceIds[$source.id] = $true }

foreach ($corpus in $corpora) {
    foreach ($field in @('id', 'source_id', 'culture_id', 'script_id', 'language_id', 'ranges', 'state')) {
        if (-not $corpus.PSObject.Properties.Name.Contains($field) -or
            [string]::IsNullOrWhiteSpace($corpus.$field)) {
            $errors.Add("CORPUS $($corpus.id) missing $field")
        }
    }
    if (-not $sourceIds.ContainsKey($corpus.source_id)) {
        $errors.Add("CORPUS $($corpus.id) references unknown source $($corpus.source_id)")
    }
    if ($corpus.state -notin $allowedStates) {
        $errors.Add("CORPUS $($corpus.id) has invalid state $($corpus.state)")
    }
}

$duplicateCorpora = $corpora | Group-Object id | Where-Object Count -gt 1
foreach ($duplicate in $duplicateCorpora) {
    $errors.Add("Duplicate CORPUS id $($duplicate.Name)")
}

if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Error $_ }
    throw "Manifest validation failed with $($errors.Count) error(s)."
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Manifest).Hash.ToLowerInvariant()
Write-Output "CORPUS_MANIFEST_PASS|sources=$($sources.Count)|corpora=$($corpora.Count)|sha256=$hash|json=0"
