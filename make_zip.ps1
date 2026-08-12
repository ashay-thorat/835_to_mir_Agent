# ── make_zip.ps1 ──────────────────────────────────────────────────
# Creates a clean, shareable zip of the 835_to_mir_app project.
# Excludes virtual-envs, caches, node_modules, runtime data, and
# generated output so the recipient gets only source + config.
# Usage:  powershell -ExecutionPolicy Bypass -File make_zip.ps1
# ──────────────────────────────────────────────────────────────────

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ZipName     = "835_to_mir_app.zip"
$ZipPath     = Join-Path $ProjectRoot $ZipName

# Folders to skip (case-insensitive)
$ExcludeDirs = @(
    '.venv',
    '__pycache__',
    '.pytest_cache',
    'node_modules',
    '.git',
    'data',
    'output',
    'generated',
    'logs',
    'dist',            # frontend build output
    '.gemini'
)

# File patterns to skip
$ExcludeFiles = @(
    '*.pyc',
    '*.pyo',
    '*.zip',
    '.env',
    '*.log'
)

# Remove old zip if present
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

# Collect files, filtering out excluded dirs and patterns
$files = Get-ChildItem -Path $ProjectRoot -Recurse -File | Where-Object {
    $rel = $_.FullName.Substring($ProjectRoot.Length + 1)
    $parts = $rel -split '[/\\]'

    # Skip if any path segment is an excluded directory
    $dominated = $false
    foreach ($dir in $ExcludeDirs) {
        foreach ($part in $parts) {
            if ($part -ieq $dir) { $dominated = $true; break }
        }
        if ($dominated) { break }
    }
    if ($dominated) { return $false }

    # Skip excluded file patterns
    foreach ($pat in $ExcludeFiles) {
        if ($_.Name -like $pat) { return $false }
    }
    return $true
}

# Build the zip
$files | Compress-Archive -DestinationPath $ZipPath -Force

$count = $files.Count
$sizeMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)
Write-Host ""
Write-Host "Done!  $ZipName  ($count files, $sizeMB MB)" -ForegroundColor Green
Write-Host "Location: $ZipPath"
