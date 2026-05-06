# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Shared configuration for the Nanvix BusyBox build system."""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Platform defaults
# ---------------------------------------------------------------------------

DOCKER_IMAGE = "nanvix/toolchain:latest-minimal"
DEFAULT_PLATFORM = "microvm"
DEFAULT_PROCESS_MODE = "standalone"
DEFAULT_MEMORY_SIZE = "128mb"
DEFAULT_INSTALL_PREFIX = "/sysroot"

# ELF suffix for cross-compiled binaries
EXE = ".elf"

# ---------------------------------------------------------------------------
# Toolchain
# ---------------------------------------------------------------------------

TOOLCHAIN_TRIPLET = "i686-nanvix"
TOOLCHAIN_DEFAULT_PATH = "/opt/nanvix"

# Docker-internal paths
DOCKER_TOOLCHAIN_PATH = "/opt/nanvix"
DOCKER_SYSROOT_PATH = "/mnt/sysroot"
DOCKER_WORKSPACE_PATH = "/mnt/workspace"


def toolchain_paths(
    toolchain: str | Path,
    sysroot: str | Path,
) -> dict[str, Path]:
    """Return resolved paths to toolchain binaries and libraries."""
    tc = Path(toolchain)
    sr = Path(sysroot)
    return {
        "cc": tc / "bin" / f"{TOOLCHAIN_TRIPLET}-gcc",
        "cxx": tc / "bin" / f"{TOOLCHAIN_TRIPLET}-g++",
        "ld": tc / "bin" / f"{TOOLCHAIN_TRIPLET}-ld",
        "ar": tc / "bin" / f"{TOOLCHAIN_TRIPLET}-ar",
        "ranlib": tc / "bin" / f"{TOOLCHAIN_TRIPLET}-ranlib",
        "strip": tc / "bin" / f"{TOOLCHAIN_TRIPLET}-strip",
        "libc": tc / f"{TOOLCHAIN_TRIPLET}" / "lib" / "libc.a",
        "libm": tc / f"{TOOLCHAIN_TRIPLET}" / "lib" / "libm.a",
        "libposix": sr / "lib" / "libposix.a",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IS_WINDOWS = sys.platform == "win32"


def nanvixd_binary() -> str:
    """Return the nanvixd binary name for the current platform."""
    if IS_WINDOWS:
        return "nanvixd.exe"
    return "nanvixd.elf"


def mkramfs_binary() -> str:
    """Return the mkramfs binary name for the current platform."""
    if IS_WINDOWS:
        return "mkramfs.exe"
    return "mkramfs.elf"
