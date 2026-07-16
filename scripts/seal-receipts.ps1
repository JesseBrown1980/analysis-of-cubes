param(
  [switch]$Verify
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$sumsPath = Join-Path $root 'SHA256SUMS'
$masterSidecarPath = Join-Path $root 'SHA256SUMS.sha256'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$utf8Strict = New-Object System.Text.UTF8Encoding($false, $true)
$hasGetRelativePath = [bool](
  [System.IO.Path].GetMethods() |
    Where-Object {
      $_.Name -eq 'GetRelativePath' -and
      $_.IsStatic -and
      $_.GetParameters().Count -eq 2
    } |
    Select-Object -First 1
)

function Get-RepoRelativePath {
  param([Parameter(Mandatory = $true)][string]$FullName)

  $fullPath = [System.IO.Path]::GetFullPath($FullName)
  if ($script:hasGetRelativePath) {
    $relative = [System.IO.Path]::GetRelativePath($script:root, $fullPath)
  } else {
    # Windows PowerShell 5.1 predates Path.GetRelativePath. Current
    # cross-platform PowerShell uses Path.GetRelativePath above.
    $separator = [System.IO.Path]::DirectorySeparatorChar
    $rootWithSeparator = $script:root.TrimEnd(
      [System.IO.Path]::DirectorySeparatorChar,
      [System.IO.Path]::AltDirectorySeparatorChar
    ) + $separator
    $rootUri = New-Object System.Uri($rootWithSeparator)
    $fullUri = New-Object System.Uri($fullPath)
    $relative = [System.Uri]::UnescapeDataString(
      $rootUri.MakeRelativeUri($fullUri).ToString()
    )
  }

  $normalized = $relative.Replace('\', '/')
  if (
    [System.IO.Path]::IsPathRooted($relative) -or
    $normalized -eq '..' -or
    $normalized.StartsWith('../', [System.StringComparison]::Ordinal)
  ) {
    throw "Path escaped repository root: $FullName"
  }
  return $normalized
}

function Invoke-GitPayloadList {
  $startInfo = New-Object System.Diagnostics.ProcessStartInfo
  $startInfo.FileName = 'git'
  $startInfo.Arguments = 'ls-files -z --cached --others --exclude-standard'
  $startInfo.WorkingDirectory = $script:root
  $startInfo.UseShellExecute = $false
  $startInfo.CreateNoWindow = $true
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  if ($startInfo.PSObject.Properties.Name -contains 'StandardOutputEncoding') {
    $startInfo.StandardOutputEncoding = $script:utf8NoBom
    $startInfo.StandardErrorEncoding = $script:utf8NoBom
  }

  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $startInfo
  [void]$process.Start()
  $stdout = $process.StandardOutput.ReadToEnd()
  $stderr = $process.StandardError.ReadToEnd()
  $process.WaitForExit()
  if ($process.ExitCode -ne 0) {
    throw "git ls-files failed ($($process.ExitCode)): $($stderr.Trim())"
  }

  [string[]]$paths = @(
    $stdout.Split(
      [char[]]@([char]0),
      [System.StringSplitOptions]::RemoveEmptyEntries
    ) |
      Where-Object {
        $_ -cne 'SHA256SUMS' -and
        $_ -cne 'SHA256SUMS.sha256'
      }
  )
  [System.Array]::Sort($paths, [System.StringComparer]::Ordinal)
  return $paths
}

function Get-PayloadFiles {
  [object[]]$payload = @()
  foreach ($gitPath in (Invoke-GitPayloadList)) {
    if ($gitPath.IndexOfAny([char[]]@("`r", "`n")) -ge 0) {
      throw "Payload path cannot be represented in SHA256SUMS: $gitPath"
    }

    $nativePath = $gitPath.Replace(
      '/',
      [System.IO.Path]::DirectorySeparatorChar
    )
    $fullName = [System.IO.Path]::GetFullPath(
      (Join-Path $script:root $nativePath)
    )
    $relative = Get-RepoRelativePath -FullName $fullName
    if ($relative -cne $gitPath) {
      throw "Non-canonical Git payload path: git=$gitPath filesystem=$relative"
    }
    if (-not [System.IO.File]::Exists($fullName)) {
      throw "Payload is not a regular file or is missing: $relative"
    }

    $payload += [pscustomobject]@{
      Relative = $relative
      FullName = $fullName
    }
  }
  return $payload
}

function Get-Sha256 {
  param([Parameter(Mandatory = $true)][string]$Path)
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Write-LfNoBom {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$Lines
  )

  $rows = @($Lines)
  $content = [string]::Join("`n", $rows)
  if ($rows.Count -gt 0) {
    $content += "`n"
  }
  [System.IO.File]::WriteAllText($Path, $content, $script:utf8NoBom)
}

function Read-LfNoBom {
  param([Parameter(Mandatory = $true)][string]$Path)

  $bytes = [System.IO.File]::ReadAllBytes($Path)
  if (
    $bytes.Length -ge 3 -and
    $bytes[0] -eq 0xEF -and
    $bytes[1] -eq 0xBB -and
    $bytes[2] -eq 0xBF
  ) {
    throw "UTF-8 BOM is not allowed: $Path"
  }
  $text = $script:utf8Strict.GetString($bytes)
  if ($text.Contains("`r")) {
    throw "CR/CRLF is not allowed: $Path"
  }
  if (
    $text.Length -gt 0 -and
    -not $text.EndsWith("`n", [System.StringComparison]::Ordinal)
  ) {
    throw "Final LF is missing: $Path"
  }
  return $text
}

function Read-HashRows {
  param([Parameter(Mandatory = $true)][string]$Path)

  [object[]]$rows = @()
  $seen = New-Object 'System.Collections.Generic.HashSet[string]' (
    [System.StringComparer]::Ordinal
  )
  $text = Read-LfNoBom -Path $Path
  foreach ($line in @(
    $text.Split(
      [char[]]@("`n"),
      [System.StringSplitOptions]::RemoveEmptyEntries
    )
  )) {
    if ($line -cnotmatch '^([0-9a-f]{64})  (.+)$') {
      throw "Malformed SHA-256 row in $Path`: $line"
    }
    $relative = $Matches[2]
    if (-not $seen.Add($relative)) {
      throw "Duplicate SHA-256 path in $Path`: $relative"
    }
    $rows += [pscustomobject]@{
      Hash = $Matches[1]
      Relative = $relative
    }
  }
  return $rows
}

function New-OrdinalSet {
  return New-Object 'System.Collections.Generic.HashSet[string]' (
    [System.StringComparer]::Ordinal
  )
}

function Get-PayloadFile {
  param(
    [Parameter(Mandatory = $true)][object[]]$Payload,
    [Parameter(Mandatory = $true)][string]$Relative
  )
  return @(
    $Payload |
      Where-Object { $_.Relative -ceq $Relative } |
      Select-Object -First 1
  )[0]
}

function Test-AllReceipts {
  param([Parameter(Mandatory = $true)][object[]]$Payload)

  [string[]]$failures = @()
  [object[]]$rootRows = @()

  if (-not [System.IO.File]::Exists($script:sumsPath)) {
    $failures += 'MISSING SHA256SUMS'
  } else {
    try {
      $rootRows = @(Read-HashRows -Path $script:sumsPath)
    } catch {
      $failures += "INVALID SHA256SUMS $($_.Exception.Message)"
    }
  }

  if (-not [System.IO.File]::Exists($script:masterSidecarPath)) {
    $failures += 'MISSING SHA256SUMS.sha256'
  } elseif ([System.IO.File]::Exists($script:sumsPath)) {
    try {
      $masterRows = @(Read-HashRows -Path $script:masterSidecarPath)
      if ($masterRows.Count -ne 1) {
        $failures += "MASTER_SIDECAR_ROWS expected=1 actual=$($masterRows.Count)"
      } else {
        if ($masterRows[0].Relative -cne 'SHA256SUMS') {
          $failures += "MASTER_SIDECAR_PATH $($masterRows[0].Relative)"
        }
        if ($masterRows[0].Hash -cne (Get-Sha256 -Path $script:sumsPath)) {
          $failures += 'MASTER_SIDECAR_MISMATCH SHA256SUMS'
        }
      }
    } catch {
      $failures += "INVALID SHA256SUMS.sha256 $($_.Exception.Message)"
    }
  }

  $payloadSet = New-OrdinalSet
  foreach ($file in $Payload) {
    [void]$payloadSet.Add($file.Relative)
  }
  $rootSet = New-OrdinalSet
  foreach ($row in $rootRows) {
    [void]$rootSet.Add($row.Relative)
  }
  foreach ($relative in $payloadSet) {
    if (-not $rootSet.Contains($relative)) {
      $failures += "ROOT_ROW_MISSING $relative"
    }
  }
  foreach ($relative in $rootSet) {
    if (-not $payloadSet.Contains($relative)) {
      $failures += "ROOT_ROW_EXTRA $relative"
    }
  }

  foreach ($row in $rootRows) {
    $file = Get-PayloadFile -Payload $Payload -Relative $row.Relative
    if ($null -eq $file) {
      continue
    }
    if ($row.Hash -cne (Get-Sha256 -Path $file.FullName)) {
      $failures += "ROOT_HASH_MISMATCH $($row.Relative)"
    }
  }

  $receiptFiles = @(
    $Payload |
      Where-Object {
        $extension = [System.IO.Path]::GetExtension($_.Relative)
        $extension -ieq '.hbp' -or $extension -ieq '.hbi'
      }
  )
  foreach ($file in $receiptFiles) {
    $sidecarRelative = "$($file.Relative).sha256"
    $sidecarFullName = "$($file.FullName).sha256"
    if (-not [System.IO.File]::Exists($sidecarFullName)) {
      $failures += "RECEIPT_SIDECAR_MISSING $sidecarRelative"
      continue
    }
    if (-not $payloadSet.Contains($sidecarRelative)) {
      $failures += "RECEIPT_SIDECAR_NOT_PAYLOAD $sidecarRelative"
    }
    try {
      $sidecarRows = @(Read-HashRows -Path $sidecarFullName)
      if ($sidecarRows.Count -ne 1) {
        $failures += "RECEIPT_SIDECAR_ROWS $sidecarRelative"
        continue
      }
      if ($sidecarRows[0].Relative -cne $file.Relative) {
        $failures += "RECEIPT_SIDECAR_PATH $sidecarRelative"
      }
      if ($sidecarRows[0].Hash -cne (Get-Sha256 -Path $file.FullName)) {
        $failures += "RECEIPT_SIDECAR_MISMATCH $($file.Relative)"
      }
    } catch {
      $failures += "INVALID_RECEIPT_SIDECAR $sidecarRelative $($_.Exception.Message)"
    }
  }

  if ($failures.Count -gt 0) {
    foreach ($failure in $failures) {
      Write-Error -Message $failure -ErrorAction Continue
    }
    return $false
  }
  return $true
}

if ($Verify) {
  $payload = @(Get-PayloadFiles)
  if (-not (Test-AllReceipts -Payload $payload)) {
    exit 1
  }
  $receiptCount = @(
    $payload |
      Where-Object {
        $extension = [System.IO.Path]::GetExtension($_.Relative)
        $extension -ieq '.hbp' -or $extension -ieq '.hbi'
      }
  ).Count
  Write-Output "RECEIPTS_VERIFIED|receipts=$receiptCount|payload=$($payload.Count)|status=PASS"
  exit 0
}

$initialPayload = @(Get-PayloadFiles)
$receiptFiles = @(
  $initialPayload |
    Where-Object {
      $extension = [System.IO.Path]::GetExtension($_.Relative)
      $extension -ieq '.hbp' -or $extension -ieq '.hbi'
    }
)
foreach ($file in $receiptFiles) {
  Write-LfNoBom -Path "$($file.FullName).sha256" -Lines @(
    "$(Get-Sha256 -Path $file.FullName)  $($file.Relative)"
  )
}

# Re-enumerate after refreshing sidecars so newly created, non-ignored
# sidecars enter the exact Git payload and the root manifest.
$payload = @(Get-PayloadFiles)
$sumRows = @(
  foreach ($file in $payload) {
    "$(Get-Sha256 -Path $file.FullName)  $($file.Relative)"
  }
)
Write-LfNoBom -Path $sumsPath -Lines $sumRows
Write-LfNoBom -Path $masterSidecarPath -Lines @(
  "$(Get-Sha256 -Path $sumsPath)  SHA256SUMS"
)

Write-Output "RECEIPTS_SEALED|receipts=$($receiptFiles.Count)|payload=$($payload.Count)|status=PASS"
