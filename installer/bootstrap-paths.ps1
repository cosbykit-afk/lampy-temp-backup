<#
.SYNOPSIS
  Lampy Windows bootstrap — path stability, anchored at PGDATA.
.DESCRIPTION
  The PGDATA folder is the anchor: it is chosen first, and every other
  program's data directory is positioned relative to it (siblings under the
  anchor's parent). Creates the layout, plants NTFS junctions at hardcoded
  component paths, sets user env vars, and writes the compose .env with
  PGDATA_DIR and LAMPY_DATA.
  Run as Administrator. Idempotent: re-running with the same -PgData repairs.
  Moving: -MoveFrom <oldAnchor> -PgData <newAnchor> copies data, re-points
  junctions, rewrites compose/.env. Container-side paths never change.
.PARAMETER PgData
  The anchor: the PGDATA folder itself. Default C:\Lampy\data\pgdata.
  Must be at least two levels below a drive root. Must not be inside
  Google Drive.
.PARAMETER MoveFrom
  Previous anchor (old PGDATA path) to migrate from.
.PARAMETER Force
  Skip the Google-Drive location refusal and the move confirmation prompt.
.NOTES
  DRAFT 2026-09-19 — not yet executed on a Windows host. Syntax not yet
  verified (no PowerShell on the build machine); review before first run.
#>
param(
    [string]$PgData = "C:\Lampy\data\pgdata",
    [string]$MoveFrom = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# --- anchor and derived positions ---
$anchor   = $PgData.TrimEnd('\')                 # THE ANCHOR (pgdata itself)
$dataRoot = Split-Path $anchor -Parent           # tree the anchor heads, e.g. C:\Lampy\data
$home     = Split-Path $dataRoot -Parent         # install home, e.g. C:\Lampy
if (-not $dataRoot -or -not $home -or ($home -match '^[A-Za-z]:\\?$')) {
    throw "Anchor '$anchor' must sit at least two levels below a drive root (e.g. C:\Lampy\data\pgdata)."
}
$ollamaDir = Join-Path $dataRoot "ollama"        # siblings, relative to the anchor
$jamesDir  = Join-Path $dataRoot "james"

function Test-BadLocation {
    param([string]$Path)
    if ($Path -match 'Google Drive') { return "path contains 'Google Drive'" }
    try {
        $drv = (Get-Item $Path -ErrorAction Stop).PSDrive
        if ($drv -and $drv.DisplayRoot -match 'Google') { return "on the Google Drive virtual mount" }
    } catch { }
    return $null
}

function Set-Junction {
    param([string]$Link, [string]$Target)
    if (-not (Test-Path $Target)) {
        New-Item -ItemType Directory -Path $Target | Out-Null
    }
    if (Test-Path $Link) {
        $item = Get-Item $Link -Force
        if ($item.LinkType -eq "Junction") {
            if ($item.Target.TrimEnd('\') -ieq $Target.TrimEnd('\')) {
                Write-Host "junction OK: $Link"
                return
            }
            Write-Host "re-pointing junction $Link -> $Target"
            $item.Delete()  # removes the link itself, not the target
        } else {
            throw "$Link exists and is not a junction — refusing to touch it. Move it aside first."
        }
    }
    New-Item -ItemType Junction -Path $Link -Target $Target | Out-Null
    Write-Host "junction: $Link -> $Target"
}

function Set-UserEnv {
    param([string]$Name, [string]$Value)
    [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    Set-Item -Path "env:$Name" -Value $Value
    Write-Host "env: $Name=$Value"
}

# --- sanity ---
$bad = Test-BadLocation $anchor
if ($bad -and -not $Force) {
    throw "Refusing: anchor $anchor is $bad. Pick a local anchor, or use -Force to override."
}

# --- move mode: copy data, then fall through to re-point everything ---
if ($MoveFrom -ne "") {
    $oldAnchor = $MoveFrom.TrimEnd('\')
    $oldRoot   = Split-Path $oldAnchor -Parent
    if (-not (Test-Path (Join-Path $oldRoot "lampy-anchor.marker"))) {
        throw "$oldRoot has no lampy-anchor.marker — not a Lampy data tree. Aborting."
    }
    if (-not $Force) {
        $ans = Read-Host "Copy data from $oldAnchor to $anchor and re-point junctions? Type YES to proceed"
        if ($ans -ne "YES") { throw "aborted by user" }
    }
    foreach ($d in @("pgdata", "ollama", "james")) {
        $src = Join-Path $oldRoot $d
        $dst = Join-Path $dataRoot $d
        if (Test-Path $src) {
            robocopy $src $dst /MIR /COPY:DAT /R:2 /W:2 /NFL /NDL | Out-Null
            if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $d (exit $LASTEXITCODE)" }
            Write-Host "copied: $d"
        }
    }
}

# --- layout: anchor first, siblings extend off its tree; home above ---
foreach ($p in @($anchor, $ollamaDir, $jamesDir)) {
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
}
foreach ($d in @("bin", "compose", "conf", "htdocs", "logs")) {
    $p = Join-Path $home $d
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
}
Set-Content -Path (Join-Path $dataRoot "lampy-anchor.marker") -Value $anchor

# --- junction armor at hardcoded locations ---
Set-Junction (Join-Path $env:USERPROFILE ".ollama") $ollamaDir

# --- user env vars ---
Set-UserEnv "PGDATA" $anchor
Set-UserEnv "LAMPY_DATA" $dataRoot
Set-UserEnv "LAMPY_HOME" $home
Set-UserEnv "OLLAMA_MODELS" $ollamaDir

# --- compose .env (anchor-derived bind mounts) ---
$envFile = Join-Path $home "compose\.env"
Set-Content -Path $envFile -Value "PGDATA_DIR=$anchor`nLAMPY_DATA=$dataRoot"
Write-Host "wrote: $envFile"

Write-Host "OK: anchor at $anchor; data tree $dataRoot; home $home"
