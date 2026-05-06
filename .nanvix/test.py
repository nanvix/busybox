# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Test orchestration for Nanvix BusyBox.

Provides staging, smoke tests (echo, true), and interactive shell launch.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import sys as _sys

_sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_sibling

config = load_sibling("config", __file__)
ramfs_mod = load_sibling("ramfs", __file__)


def run_all(
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
    """Run the BusyBox smoke test suite on Nanvix."""
    nanvix_home = Path(sysroot)

    # Prepare staging area
    print("Preparing staging area...")
    staging = ramfs_mod.prepare_staging(repo_root, nanvix_home)

    # Build ramfs image
    ramfs_img = repo_root / ".nanvix" / "busybox-ramfs.img"
    ramfs_mod.build_image(staging, nanvix_home, output=ramfs_img)

    # Locate nanvixd
    nanvixd = staging / "sysroot" / "bin" / config.nanvixd_binary()
    if not nanvixd.is_file():
        nanvixd = nanvix_home / "bin" / config.nanvixd_binary()
    if not nanvixd.is_file():
        raise FileNotFoundError(
            f"{config.nanvixd_binary()} not found. Ensure Nanvix is built."
        )

    bin_dir = staging / "sysroot" / "bin"
    busybox_guest = f"./bin/busybox{config.EXE}"

    # Test 1: busybox true (exit code 0)
    print("\n--- Test 1: busybox true ---")
    _run_nanvixd(
        nanvixd, bin_dir, ramfs_img,
        busybox_guest, "true",
        test_name="true",
    )

    # Test 2: busybox echo
    print("\n--- Test 2: busybox echo ---")
    _run_nanvixd(
        nanvixd, bin_dir, ramfs_img,
        busybox_guest, "echo Hello from BusyBox on Nanvix!",
        test_name="echo",
    )

    # Test 3: busybox ash -c 'echo shell works'
    print("\n--- Test 3: busybox ash -c ---")
    _run_nanvixd(
        nanvixd, bin_dir, ramfs_img,
        busybox_guest, "ash -c 'echo BusyBox shell is running on Nanvix'",
        test_name="ash",
    )

    print("\n=== All BusyBox smoke tests passed! ===")


def _run_nanvixd(
    nanvixd: Path,
    bin_dir: Path,
    ramfs_img: Path,
    guest_binary: str,
    guest_args: str,
    *,
    test_name: str = "",
    timeout: int = 60,
) -> None:
    """Run a command via nanvixd and check for success."""
    cmd = [
        str(nanvixd),
        "-bin-dir", str(bin_dir),
        "-ramfs", str(ramfs_img),
        "--",
        guest_binary,
        guest_args,
    ]

    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.stdout:
        print(f"  stdout: {result.stdout.strip()}")
    if result.stderr:
        print(f"  stderr: {result.stderr.strip()}")

    if result.returncode != 0:
        raise RuntimeError(
            f"Test '{test_name}' failed with exit code {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    print(f"  PASS: {test_name}")
