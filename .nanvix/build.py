# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Build orchestration for Nanvix BusyBox cross-compilation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import sys as _sys

_sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_sibling

config = load_sibling("config", __file__)


def make_args(
    sysroot: str | Path,
    toolchain: str | Path,
    *targets: str,
    platform: str = config.DEFAULT_PLATFORM,
    process_mode: str = config.DEFAULT_PROCESS_MODE,
    memory_size: str = config.DEFAULT_MEMORY_SIZE,
) -> list[str]:
    """Build the make argument list for Makefile.nanvix."""
    sysroot_p = Path(sysroot)
    toolchain_p = Path(toolchain)

    args = [
        "make",
        "-f",
        "Makefile.nanvix",
        "CONFIG_NANVIX=y",
        f"NANVIX_HOME={sysroot_p}",
        f"NANVIX_TOOLCHAIN={toolchain_p}",
        f"PLATFORM={platform}",
        f"PROCESS_MODE={process_mode}",
        f"MEMORY_SIZE={memory_size}",
    ]
    args.extend(targets)
    return args


def run_make(
    args: list[str],
    *,
    cwd: Path | None = None,
    run_fn: Any = None,
) -> None:
    """Execute a make command."""
    if run_fn:
        run_fn(*args, cwd=cwd)
    else:
        subprocess.run(args, cwd=cwd, check=True)


def build(
    sysroot: str | Path,
    toolchain: str | Path,
    repo_root: Path,
    *,
    platform: str = config.DEFAULT_PLATFORM,
    process_mode: str = config.DEFAULT_PROCESS_MODE,
    memory_size: str = config.DEFAULT_MEMORY_SIZE,
    run_fn: Any = None,
    docker: bool = False,
) -> None:
    """Cross-compile busybox.elf for Nanvix."""
    effective_sysroot = config.DOCKER_SYSROOT_PATH if docker else sysroot
    effective_toolchain = config.DOCKER_TOOLCHAIN_PATH if docker else toolchain
    args = make_args(
        effective_sysroot,
        effective_toolchain,
        "build",
        platform=platform,
        process_mode=process_mode,
        memory_size=memory_size,
    )
    run_make(args, cwd=repo_root, run_fn=run_fn)


def install(
    sysroot: str | Path,
    toolchain: str | Path,
    repo_root: Path,
    destdir: Path,
    *,
    platform: str = config.DEFAULT_PLATFORM,
    process_mode: str = config.DEFAULT_PROCESS_MODE,
    memory_size: str = config.DEFAULT_MEMORY_SIZE,
    run_fn: Any = None,
    docker: bool = False,
) -> None:
    """Install BusyBox into a staging directory."""
    effective_sysroot = config.DOCKER_SYSROOT_PATH if docker else sysroot
    effective_toolchain = config.DOCKER_TOOLCHAIN_PATH if docker else toolchain
    try:
        rel_destdir = destdir.resolve().relative_to(repo_root.resolve())
    except ValueError:
        rel_destdir = destdir
    args = make_args(
        effective_sysroot,
        effective_toolchain,
        "install",
        f"DESTDIR={rel_destdir}",
        platform=platform,
        process_mode=process_mode,
        memory_size=memory_size,
    )
    run_make(args, cwd=repo_root, run_fn=run_fn)


def clean(repo_root: Path) -> None:
    """Remove build artifacts."""
    subprocess.run(
        ["make", "-f", "Makefile.nanvix", "clean"],
        cwd=repo_root,
        check=False,
    )


# Git-clean exclusion list — files preserved during distclean.
_DISTCLEAN_EXCLUDES: list[str] = [
    "Makefile.nanvix",
    "NANVIX.md",
    ".github",
    ".nanvix/",
    "configs/nanvix_defconfig",
    "z",
    "z.sh",
    "z.ps1",
]


def distclean(repo_root: Path) -> None:
    """Deep clean: remove all build artifacts and untracked files."""
    clean(repo_root)
    cmd = ["git", "clean", "-fdx"]
    for exc in _DISTCLEAN_EXCLUDES:
        cmd.extend(["-e", exc])
    subprocess.run(cmd, cwd=repo_root, check=True)
