[CmdletBinding()]
param(
    [string]$CorpusRoot,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$scriptRoot = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($scriptRoot)) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ([string]::IsNullOrWhiteSpace($CorpusRoot)) {
    $CorpusRoot = Join-Path $scriptRoot '..\corpora'
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

function Write-LfUtf8NoBom {
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [Parameter(Mandatory)]
        [string[]]$Lines
    )
    [System.IO.File]::WriteAllText($Path, (($Lines -join "`n") + "`n"), $utf8NoBom)
}

function Write-ShaSidecar {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    Write-LfUtf8NoBom -Path "$Path.sha256" -Lines @("$hash  $(Split-Path -Leaf $Path)")
    return $hash
}

function Get-CsvDataRowCount {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )
    $count = 0
    $reader = [System.IO.File]::OpenText($Path)
    try {
        $null = $reader.ReadLine()
        while ($null -ne ($line = $reader.ReadLine())) {
            if (-not [string]::IsNullOrWhiteSpace($line)) {
                $count++
            }
        }
    }
    finally {
        $reader.Dispose()
    }
    return $count
}

function Acquire-TapCsv {
    param(
        [Parameter(Mandatory)]
        [string]$CorpusId,
        [Parameter(Mandatory)]
        [string]$Authority,
        [Parameter(Mandatory)]
        [string]$Endpoint,
        [Parameter(Mandatory)]
        [hashtable]$PostBody,
        [Parameter(Mandatory)]
        [string]$Query,
        [Parameter(Mandatory)]
        [string]$LicenseUri,
        [Parameter(Mandatory)]
        [string]$OutputName,
        [Parameter(Mandatory)]
        [int]$ExpectedRows,
        [Parameter(Mandatory)]
        [string]$Boundary
    )

    $sourceDir = Join-Path $CorpusRoot "$CorpusId\source"
    New-Item -ItemType Directory -Force -Path $sourceDir | Out-Null
    $csvPath = Join-Path $sourceDir $OutputName
    if ((Test-Path -LiteralPath $csvPath -PathType Leaf) -and -not $Force) {
        throw "Refusing to overwrite existing seed without -Force: $csvPath"
    }

    Invoke-WebRequest `
        -UseBasicParsing `
        -Method Post `
        -Uri $Endpoint `
        -Body $PostBody `
        -ContentType 'application/x-www-form-urlencoded' `
        -OutFile $csvPath

    $bytes = (Get-Item -LiteralPath $csvPath).Length
    $rawHash = Write-ShaSidecar -Path $csvPath
    $rows = Get-CsvDataRowCount -Path $csvPath
    if ($rows -ne $ExpectedRows) {
        throw "$CorpusId returned $rows data rows; expected exactly $ExpectedRows"
    }

    $receiptPath = Join-Path $sourceDir 'CORPUS.hbp'
    Write-LfUtf8NoBom -Path $receiptPath -Lines @(
        "CORPUSHDR|schema=ASTRO_TAP_CSV_V1|corpus=$CorpusId|state=MEASURED_ACQUIRED|json=0",
        "SOURCE|authority=$Authority|endpoint=$Endpoint|http_method=POST|format=csv|license_uri=$LicenseUri|query=$Query|json=0",
        "RAW|file=$OutputName|bytes=$bytes|rows=$rows|sha256=$rawHash|ordering=QUERY_ORDER|json=0",
        "NORMALIZATION|raw_response_preserved=1|receipt_encoding=UTF8_NO_BOM_LF|csv_rewrite=0|json=0",
        "BOUNDARY|$Boundary|physical_inference_claimed=0|claims_final_apex=0|json=0"
    )
    $receiptHash = Write-ShaSidecar -Path $receiptPath
    Write-Output "COSMOS_SEED_PASS|id=$CorpusId|rows=$rows|bytes=$bytes|raw_sha256=$rawHash|receipt_sha256=$receiptHash|json=0"
}

$exoplanetQuery = 'select top 256 pl_name,hostname,default_flag,sy_snum,sy_pnum,pl_orbper,pl_orbsmax,pl_rade,pl_bmasse,st_teff,st_rad,st_mass,ra,dec,sy_dist from ps where default_flag=1 order by hostname,pl_name'
Acquire-TapCsv `
    -CorpusId 'nasa-exoplanet-archive' `
    -Authority 'NASA_Caltech_IPAC_Exoplanet_Archive' `
    -Endpoint 'https://exoplanetarchive.ipac.caltech.edu/TAP/sync' `
    -PostBody @{ query = $exoplanetQuery; format = 'csv' } `
    -Query $exoplanetQuery `
    -LicenseUri 'https://exoplanetarchive.ipac.caltech.edu/docs/acknowledge.html' `
    -OutputName 'ps-default-top-256.csv' `
    -ExpectedRows 256 `
    -Boundary 'PS_rows_are_self_consistent_per_default_reference_but_archive_values_remain_literature_measurements_with_source_uncertainties'

$gaiaQuery = 'select source_id,random_index,ra,dec,parallax,parallax_error,pmra,pmra_error,pmdec,pmdec_error,radial_velocity,radial_velocity_error,phot_g_mean_mag,bp_rp,ruwe from gaiadr3.gaia_source where random_index < 4096 order by random_index'
Acquire-TapCsv `
    -CorpusId 'gaia-dr3' `
    -Authority 'ESA_Gaia_DPAC' `
    -Endpoint 'https://gea.esac.esa.int/tap-server/tap/sync' `
    -PostBody @{ REQUEST = 'doQuery'; LANG = 'ADQL'; FORMAT = 'csv'; QUERY = $gaiaQuery } `
    -Query $gaiaQuery `
    -LicenseUri 'https://www.cosmos.esa.int/web/gaia-users/credits' `
    -OutputName 'gaia-dr3-random-index-0000-4095.csv' `
    -ExpectedRows 4096 `
    -Boundary 'random_index_subset_is_deterministic_for_Gaia_DR3_and_null_measurements_are_preserved_without_imputation'
