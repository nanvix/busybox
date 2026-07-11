# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

# Thin wrapper that delegates to the nanvix-zutil CLI.
# Self-bootstraps nanvix-zutil into .nanvix\venv\ if it is not already installed.

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ZArgs
)

$ErrorActionPreference = 'Stop'

# z.ps1 lives at the repository root, so use its directory directly
# instead of relying on git to discover the top-level checkout directory.
$repoRoot = $PSScriptRoot
$versionFile = Join-Path $repoRoot ".zutils-version"
if (-not (Test-Path -LiteralPath $versionFile)) {
    throw "Error: $versionFile not found."
}
$zutilVersion = (Get-Content -LiteralPath $versionFile -Raw).Trim() -replace "^v", ""
$venvDir = Join-Path $repoRoot ".nanvix\venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvZutil = Join-Path $venvDir "Scripts\nanvix-zutil.exe"

# Windows compatibility shim: nanvix-zutil references os.getuid/os.getgid
# which are unavailable on Windows.  Stub them before importing the package.
# NOTE: Use single quotes inside the Python code so that PowerShell does not
# strip the quotes when passing the string to python.exe -c.
$ShimCode = @'
import os,sys;os.getuid=getattr(os,'getuid',lambda:0);os.getgid=getattr(os,'getgid',lambda:0);from nanvix_zutil.__main__ import main;sys.exit(main())
'@

$zutilGlobalVersion = try {
    & nanvix-zutil --version 2>$null
}
catch {
    $null
}

function Find-Python312 {
    $candidates = @(
        @{ Command = "py"; Prefix = @("-3.12") },
        @{ Command = "python3.12"; Prefix = @() },
        @{ Command = "python"; Prefix = @() },
        @{ Command = "python3"; Prefix = @() }
    )
    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) {
            continue
        }
        $checkArgs = @($candidate.Prefix) + @(
            "-c",
            "import sys; raise SystemExit(sys.version_info < (3, 12))"
        )
        & $candidate.Command @checkArgs 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $candidate
        }
    }
    throw "Python 3.12 or newer is required by nanvix-zutil."
}

function Bootstrap {
    # Pin nanvix-zutil version for reproducible bootstrapping.
    Write-Information "nanvix-zutil not found -- bootstrapping nanvix-zutil==${zutilVersion}..." -InformationAction Continue

    $wheelUrl = "https://github.com/nanvix/zutils/releases/download/v${zutilVersion}/nanvix_zutil-${zutilVersion}-py3-none-any.whl"

    $python = Find-Python312
    $venvArgs = @("-m", "venv")
    if (Test-Path $venvDir) {
        $venvArgs += "--clear"
    }
    $venvArgs += $venvDir

    $pythonArgs = @($python.Prefix) + $venvArgs
    & $python.Command @pythonArgs
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "venv creation failed (exit code $LASTEXITCODE)"
    }
    & $venvPython -m pip install --quiet "nanvix-zutil[lint] @ $($wheelUrl)"
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "pip install failed (exit code $LASTEXITCODE)"
    }
}

# Prefer the venv copy if it exists; otherwise use the global install.
$bin = $null
if ((-not (Test-Path $venvDir)) -and (-not $zutilGlobalVersion)) {
    Bootstrap
    if (-not (Test-Path $venvZutil)) {
        throw "Bootstrap completed but $venvZutil not found."
    }
    $bin = $venvZutil
}
elseif (Test-Path $venvZutil) {
    # Use the shim to check version -- running the exe directly fails on
    # Windows because os.getuid/os.getgid are unavailable (see FIXME above).
    $venvVersion = try {
        & $venvPython -c $ShimCode --version 2>$null
    }
    catch {
        $null
    }
    if ($venvVersion -ne "nanvix-zutil ${zutilVersion}") {
        Write-Warning "Venv nanvix-zutil version mismatch. Expected ${zutilVersion}, found ${venvVersion}. Re-bootstrapping..."
        Bootstrap
        if (-not (Test-Path $venvZutil)) {
            throw "Bootstrap completed but $venvZutil not found."
        }
    }
    $bin = $venvZutil
}
elseif ((Test-Path $venvDir) -and (-not $zutilGlobalVersion)) {
    Write-Warning "Incomplete venv detected (binary missing). Re-running bootstrap..."
    Bootstrap
    if (-not (Test-Path $venvZutil)) {
        throw "Bootstrap completed but $venvZutil not found."
    }
    $bin = $venvZutil
}
else {
    $bin = "nanvix-zutil"
    if ($zutilGlobalVersion -ne "nanvix-zutil ${zutilVersion}") {
        Write-Warning "nanvix-zutil global install does not match expected version. Expected ${zutilVersion}, found ${zutilGlobalVersion}."
        Bootstrap
        if (-not (Test-Path $venvZutil)) {
            throw "Bootstrap completed but $venvZutil not found."
        }
        $bin = $venvZutil
    }
}

if ($bin -eq $venvZutil) {
    & $venvPython -c $ShimCode @ZArgs
}
else {
    & $bin @ZArgs
}

$ec = $LASTEXITCODE

# On Windows the venv's python.exe is locked while it runs, so the Python
# distclean command cannot delete it.  Now that the interpreter has exited the
# lock is released and the shell can safely remove the venv directory.
if ($ZArgs -and $ZArgs[0] -eq "distclean" -and (Test-Path $venvDir)) {
    Remove-Item $venvDir -Recurse -Force -ErrorAction SilentlyContinue
}

exit $ec
