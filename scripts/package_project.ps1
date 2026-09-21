param(
    [string]$Destination = (Join-Path $PSScriptRoot "..\artifacts\aerotwin-clean-project.zip")
)

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$destinationPath = [System.IO.Path]::GetFullPath($Destination)
$stagingPath = Join-Path ([System.IO.Path]::GetTempPath()) ("aerotwin-package-" + [guid]::NewGuid().ToString("N"))
$excludedPaths = @('backend\.venv', 'backend\.env', 'backend\uploads', 'android\.gradle', 'android\local.properties')
$excludedDirectoryNames = @('.git', '.idea', 'build')

New-Item -ItemType Directory -Path $stagingPath -Force | Out-Null
try {
    Get-ChildItem -LiteralPath $projectRoot -Recurse -File -Force | Where-Object {
        $relative = $_.FullName.Substring($projectRoot.Length).TrimStart('\')
        $normalized = $relative.Replace('/', '\')
        -not ($excludedPaths | Where-Object { $normalized -eq $_ -or $normalized.StartsWith("$_\") }) -and
        -not (($normalized -split '\\') | Where-Object { $_ -in $excludedDirectoryNames }) -and
        $_.Extension -notin @('.apk', '.aab', '.iml')
    } | ForEach-Object {
        $relative = $_.FullName.Substring($projectRoot.Length).TrimStart('\')
        $target = Join-Path $stagingPath $relative
        New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target
    }
    New-Item -ItemType Directory -Path (Split-Path $destinationPath) -Force | Out-Null
    if (Test-Path -LiteralPath $destinationPath) { Remove-Item -LiteralPath $destinationPath -Force }
    Compress-Archive -Path (Join-Path $stagingPath '*') -DestinationPath $destinationPath -Force
    Write-Output "Paquete limpio creado: $destinationPath"
} finally {
    Remove-Item -LiteralPath $stagingPath -Recurse -Force -ErrorAction SilentlyContinue
}
