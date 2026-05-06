# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Ramfs image generation for Nanvix BusyBox."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import sys as _sys

_sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_sibling

config = load_sibling("config", __file__)


def build_image(
    staging: Path,
    nanvix_home: Path,
    output: Path | None = None,
) -> Path:
    """Build a ramfs image from a staged sysroot.

    Args:
        staging: Root directory containing a ``sysroot/`` subdirectory.
        nanvix_home: Path to the Nanvix sysroot (contains mkramfs).
        output: Output path for the ramfs image.

    Returns:
        Path to the generated ramfs image.
    """
    if output is None:
        raise ValueError("output path is required for build_image()")

    mkramfs_name = config.mkramfs_binary()
    mkramfs = nanvix_home / "bin" / mkramfs_name
    if not mkramfs.is_file():
        raise FileNotFoundError(
            f"{mkramfs_name} not found at {mkramfs}. "
            "Run `./z setup` first to download required binaries."
        )

    sysroot = staging / "sysroot"
    if not sysroot.is_dir():
        raise FileNotFoundError(f"{sysroot} does not exist")

    subprocess.run(
        [str(mkramfs), "-o", str(output), str(sysroot)],
        check=True,
    )

    size = output.stat().st_size
    human = _human_size(size)
    print(f"Built ramfs image: {output} ({human})")
    return output


def prepare_staging(
    repo_root: Path,
    nanvix_home: Path,
) -> Path:
    """Prepare a staging directory with BusyBox and Nanvix binaries.

    Creates .nanvix/_staging/sysroot/ with:
      - bin/busybox (the cross-compiled binary)
      - bin/nanvixd.elf, bin/kernel.elf, bin/mkramfs.elf (Nanvix runtime)
    """
    staging = repo_root / ".nanvix" / "_staging"
    sysroot = staging / "sysroot"

    # Clean previous staging
    if staging.exists():
        shutil.rmtree(staging)
    sysroot.mkdir(parents=True)

    # Copy busybox binary
    busybox_bin = repo_root / f"busybox{config.EXE}"
    if not busybox_bin.is_file():
        busybox_bin = repo_root / "busybox"
    if not busybox_bin.is_file():
        raise FileNotFoundError(
            f"busybox binary not found. Run `./z build` first."
        )

    bin_dir = sysroot / "bin"
    bin_dir.mkdir(parents=True)
    shutil.copy2(busybox_bin, bin_dir / f"busybox{config.EXE}")

    # Create applet symlinks for basic utilities
    applets = [
        "sh", "ash", "echo", "cat", "ls", "pwd", "true", "false",
        "mkdir", "rm", "rmdir", "head", "tail", "wc", "grep",
        "printf", "test", "[", "sleep", "basename", "date", "dd",
        "mv", "tr", "uname", "yes", "vi", "touch",
    ]
    for applet in applets:
        link = bin_dir / applet
        link.symlink_to(f"busybox{config.EXE}")

    # Copy Nanvix runtime binaries
    for binary in ["nanvixd.elf", "kernel.elf", "mkramfs.elf"]:
        src = nanvix_home / "bin" / binary
        if src.is_file():
            shutil.copy2(src, bin_dir / binary)

    return staging


def _human_size(nbytes: int) -> str:
    size = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
