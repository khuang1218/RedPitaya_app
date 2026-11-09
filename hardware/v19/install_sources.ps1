# Copy the reviewed overlay into the existing FPGA repository, preserving every
# overwritten source in the application review directory. Never removes files.
$ErrorActionPreference = 'Stop'
$v19Overlay = [IO.Path]::GetFullPath($PSScriptRoot)
$v19App = [IO.Path]::GetFullPath((Join-Path $v19Overlay '..\..'))
$v19Repo = [IO.Path]::GetFullPath((Join-Path $v19App '..\fpgaprj\RedPitaya-FPGA'))
$v19Backup = Join-Path $v19App 'build\tdc-v19-review\pre-v19-sources'
$v19ExpectedPath = Join-Path $v19App 'build\tdc-v19-review\install_expected.json'
$v19Expected = Get-Content -LiteralPath $v19ExpectedPath -Raw | ConvertFrom-Json
foreach ($v19Row in $v19Expected) {
    $v19Target = [IO.Path]::GetFullPath((Join-Path $v19Repo $v19Row.path))
    if (-not $v19Target.StartsWith($v19Repo + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Destination escaped FPGA repository' }
    if ($v19Row.existed) {
        if ((Get-FileHash -LiteralPath $v19Target).Hash -ne $v19Row.sha256) { throw "Source changed since review: $v19Target" }
    } elseif (Test-Path -LiteralPath $v19Target) { throw "New destination appeared since review: $v19Target" }
}
foreach ($v19Row in $v19Expected) {
    $v19Source = Join-Path $v19Overlay $v19Row.path
    $v19Target = Join-Path $v19Repo $v19Row.path
    if ($v19Row.existed) {
        $v19Saved = Join-Path $v19Backup $v19Row.path
        New-Item -ItemType Directory -Force -Path (Split-Path $v19Saved -Parent) | Out-Null
        Copy-Item -LiteralPath $v19Target -Destination $v19Saved
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $v19Target -Parent) | Out-Null
    Copy-Item -LiteralPath $v19Source -Destination $v19Target -Force
    if ((Get-FileHash -LiteralPath $v19Source).Hash -ne (Get-FileHash -LiteralPath $v19Target).Hash) { throw "Copy verification failed: $v19Target" }
}
Write-Output "Installed and verified $($v19Expected.Count) v19 files; original sources saved in $v19Backup"
