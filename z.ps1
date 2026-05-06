# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

# Thin PowerShell wrapper that delegates to the nanvix-zutil CLI.
# Self-bootstraps nanvix-zutil into .nanvix/venv/ if it is not already installed.

$ErrorActionPreference = "Stop"
$PINNED_VERSION = "0.7.43"
$ZUTIL_VERSION = if ($env:NANVIX_ZUTIL_VERSION) { $env:NANVIX_ZUTIL_VERSION -replace '^v', '' } else { $PINNED_VERSION }
$REPO_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV = Join-Path $REPO_ROOT ".nanvix" "venv"

function Get-VenvBin {
    $scripts = Join-Path $VENV "Scripts"
    if (Test-Path $scripts) {
        return @{
            Bin    = Join-Path $scripts "nanvix-zutil.exe"
            Python = Join-Path $scripts "python.exe"
        }
    }
    return @{
        Bin    = Join-Path $VENV "bin" "nanvix-zutil"
        Python = Join-Path $VENV "bin" "python"
    }
}

function Bootstrap {
    Write-Host "nanvix-zutil not found -- bootstrapping nanvix-zutil==$ZUTIL_VERSION..." -ForegroundColor Yellow
    $wheelUrl = "https://github.com/nanvix/zutils/releases/download/v${ZUTIL_VERSION}/nanvix_zutil-${ZUTIL_VERSION}-py3-none-any.whl"
    if (Test-Path $VENV) { python -m venv --clear $VENV } else { python -m venv $VENV }
    $vp = Get-VenvBin
    & $vp.Python -m pip install --quiet "nanvix-zutil[lint] @ $wheelUrl"
}

# Determine which binary to use.
$vp = Get-VenvBin
$globalVersion = try { & nanvix-zutil --version 2>$null } catch { "" }

if (-not (Test-Path $VENV) -and -not $globalVersion) {
    Bootstrap
    $BIN = (Get-VenvBin).Bin
} elseif (Test-Path $vp.Bin) {
    $venvVersion = try { & $vp.Bin --version 2>$null } catch { "" }
    if ($venvVersion -ne "nanvix-zutil $ZUTIL_VERSION") {
        Write-Host "Warning: version mismatch. Re-bootstrapping..." -ForegroundColor Yellow
        Bootstrap
    }
    $BIN = (Get-VenvBin).Bin
} else {
    $BIN = "nanvix-zutil"
}

# Extract --with-nanvix PATH
$filteredArgs = @()
$i = 0
while ($i -lt $args.Count) {
    if ($args[$i] -match '^--with-nanvix=(.+)$') {
        $env:NANVIX_LOCAL_PATH = (Resolve-Path $Matches[1]).Path
    } elseif ($args[$i] -eq '--with-nanvix') {
        $i++
        $env:NANVIX_LOCAL_PATH = (Resolve-Path $args[$i]).Path
    } else {
        $filteredArgs += $args[$i]
    }
    $i++
}

& $BIN @filteredArgs
