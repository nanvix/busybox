# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Test orchestration for Nanvix BusyBox.

Provides staging, smoke tests, and interactive shell launch.

Tests use the mkimage + ramfs approach: a system image containing
procd, memd, and busybox (as ash) is booted via nanvixd with a ramfs
image providing /bin/busybox.elf and test fixture files.  Shell
commands are piped to ash's stdin and guest stdout is checked.

Applet categories tested:
  - Shell builtins (echo, printf, test, etc.) — run in ash process.
  - NOFORK applets (basename, dirname, uname, ...) — run in ash
    process without forking.
  - NOEXEC applets (env, id, sort, head, ...) — ash forks a child
    that calls the applet function directly (no exec).
  - Regular applets (cat, grep, wc, ...) — ash forks, exec fails
    (kernel heap limit), then falls back to NOEXEC-style execution
    via a patch in shell/ash.c.

Known kernel limitations (standalone mode):
  - pipe() returns ENOTSUP — no shell pipes (|).
  - fcntl(F_DUPFD) not supported — no file redirections (>, <, >>).
  - Command substitution ($(...)) unavailable (needs pipe).
  - Regex (regcomp/regexec) stubs return NOMATCH — grep/sed regex
    patterns don't match; use grep -F for fixed-string matching.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import sys as _sys

_sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_sibling

config = load_sibling("config", __file__)
ramfs_mod = load_sibling("ramfs", __file__)


def _find_binary(name: str, *search_dirs: Path) -> Path:
    """Locate a binary in the given directories."""
    for d in search_dirs:
        p = d / name
        if p.is_file():
            return p
    raise FileNotFoundError(
        f"{name} not found in: {', '.join(str(d) for d in search_dirs)}"
    )


def _build_system_image(
    nanvix_home: Path,
    repo_root: Path,
) -> Path:
    """Create a bootable system image with procd + memd + busybox(ash).

    Returns the path to the generated image file.
    """
    mkimage = _find_binary(
        "mkimage.elf",
        nanvix_home / "bin",
        nanvix_home.parent / "bin",
    )

    # procd/memd may be in sysroot/bin, nanvix/bin, or target/
    bin_search = [
        nanvix_home / "bin",
        nanvix_home.parent / "bin",
    ]
    procd = _find_binary("procd.elf", *bin_search)
    memd = _find_binary("memd.elf", *bin_search)

    # vfsd is optional — include it when available for fork-aware FD tracking.
    vfsd: Path | None = None
    for d in bin_search:
        p = d / "vfsd.elf"
        if p.is_file():
            vfsd = p
            break

    busybox = repo_root / f"busybox{config.EXE}"
    if not busybox.is_file():
        raise FileNotFoundError(
            f"busybox binary not found at {busybox}. Run `./z build` first."
        )

    img = repo_root / ".nanvix" / "busybox-system.img"
    img.parent.mkdir(parents=True, exist_ok=True)

    mkimage_args = [
        str(mkimage), "-o", str(img),
        f"{procd};procd",
        f"{memd};memd",
    ]
    if vfsd is not None:
        mkimage_args.append(f"{vfsd};vfsd")
    mkimage_args.append(f"{busybox};ash")

    subprocess.run(mkimage_args, check=True)
    return img


def _extract_guest_output(raw_stdout: str) -> str:
    """Extract guest output from nanvixd stdout.

    Filters out the BusyBox banner, shell prompts, and blank lines
    to isolate actual command output.
    """
    lines = raw_stdout.splitlines()
    out: list[str] = []
    for line in lines:
        # Skip blank lines, BusyBox banner, and prompt-only lines
        if not line or line.startswith("BusyBox v"):
            continue
        if line.startswith("Enter 'help'"):
            continue
        if re.fullmatch(r"#\s*", line):
            continue
        # Strip leading prompt ("# ")
        if line.startswith("# "):
            line = line[2:]
        out.append(line)
    return "\n".join(out)


def _build_ramfs_image(
    nanvix_home: Path,
    repo_root: Path,
) -> Path:
    """Create a ramfs image with busybox and test fixture files.

    Returns the path to the generated ramfs image.
    """
    mkramfs = _find_binary(
        "mkramfs.elf",
        nanvix_home / "bin",
        nanvix_home.parent / "bin",
    )

    busybox = repo_root / f"busybox{config.EXE}"
    staging = repo_root / ".nanvix" / "ramfs-staging"

    # Clean and recreate staging directory
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "bin").mkdir(parents=True)
    (staging / "tmp").mkdir(parents=True)

    # Copy busybox binary
    shutil.copy2(str(busybox), str(staging / "bin" / "busybox.elf"))

    # Create test fixture files
    (staging / "tmp" / "hello.txt").write_text("hello world\n")
    (staging / "tmp" / "fruits.txt").write_text(
        "cherry\napple\nbanana\ndate\nelderberry\n"
    )
    (staging / "tmp" / "lines.txt").write_text(
        "line1\nline2\nline3\nline4\nline5\n"
    )

    img = repo_root / ".nanvix" / "busybox-ramfs.img"
    subprocess.run(
        [str(mkramfs), "-o", str(img), str(staging) + "/"],
        check=True,
    )
    return img


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

    # Build system image (procd + memd + busybox as ash)
    print("Building system image...")
    sys_img = _build_system_image(nanvix_home, repo_root)

    # Build ramfs image with test fixtures
    print("Building ramfs image...")
    ramfs_img = _build_ramfs_image(nanvix_home, repo_root)

    # Locate nanvixd and bin-dir
    nanvixd = _find_binary(
        config.nanvixd_binary(),
        nanvix_home / "bin",
        nanvix_home.parent / "bin",
    )
    bin_dir = nanvixd.parent

    passed = 0
    failed = 0
    test_num = 0

    def _test(
        name: str,
        shell_cmd: str,
        *,
        expect_in: str | None = None,
    ) -> None:
        """Run *shell_cmd* inside ash and check output.

        Args:
            name: Human-readable test name.
            shell_cmd: Command(s) piped to the ash shell via stdin.
            expect_in: Substring that must appear in the guest output.
        """
        nonlocal passed, failed, test_num
        test_num += 1
        label = f"Test {test_num}: {name}"
        try:
            result = subprocess.run(
                [
                    str(nanvixd),
                    "-bin-dir", str(bin_dir),
                    "-ramfs", str(ramfs_img),
                    "--", str(sys_img),
                ],
                input=shell_cmd + "\n",
                capture_output=True,
                text=True,
                timeout=15,
            )
            raw_out = result.stdout
        except subprocess.TimeoutExpired as te:
            # nanvixd doesn't exit when stdin closes — timeout is expected.
            # Extract whatever output was captured before the timeout.
            raw_out = te.stdout or ""
            if isinstance(raw_out, bytes):
                raw_out = raw_out.decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  FAIL: {label} ({e})")
            failed += 1
            return

        guest_out = _extract_guest_output(raw_out)

        if expect_in is not None and expect_in not in guest_out:
            print(f"  FAIL: {label}")
            print(f"    expected substring: {expect_in!r}")
            print(f"    guest output:       {guest_out!r}")
            failed += 1
            return

        print(f"  PASS: {label}")
        passed += 1

    # ==================================================================
    # Test suite
    # ==================================================================

    # --- Shell builtins ---
    _test("echo", "echo NANVIX_ECHO_OK_7X",
          expect_in="NANVIX_ECHO_OK_7X")
    _test("printf", "printf 'FMT_%s_%s\\n' ALPHA BETA",
          expect_in="FMT_ALPHA_BETA")
    _test("true exit code", "true; echo TRUE_RC_$?",
          expect_in="TRUE_RC_0")
    _test("false exit code", "false; echo FALSE_RC_$?",
          expect_in="FALSE_RC_1")
    _test("shell variable", "MYVAR=UNIQUE_VAL_93; echo $MYVAR",
          expect_in="UNIQUE_VAL_93")
    _test("shell arithmetic", "echo MATH_$((17 * 3))",
          expect_in="MATH_51")
    _test("test -f (false)", "test -f /nonexist || echo TEST_F_OK_22",
          expect_in="TEST_F_OK_22")
    _test("test string eq", "test abc = abc && echo STREQ_OK_55",
          expect_in="STREQ_OK_55")
    _test("test -n", "test -n hello && echo TESTN_OK_88",
          expect_in="TESTN_OK_88")

    # --- NOFORK applets (in-process, no fork) ---
    _test("basename", "basename /usr/local/bin/myapp.txt",
          expect_in="myapp.txt")
    _test("dirname", "dirname /usr/local/bin/myapp.txt",
          expect_in="/usr/local/bin")
    _test("printf format", "printf '%d+%d=%d\\n' 3 4 7",
          expect_in="3+4=7")
    _test("nproc", "nproc",
          expect_in="1")
    _test("realpath", "realpath /bin/../bin/sh",
          expect_in="/bin/sh")
    _test("uname", "uname",
          expect_in="nanvix")
    _test("usleep", "usleep 1000; echo USLEEP_DONE_44",
          expect_in="USLEEP_DONE_44")
    _test("logname", "logname",
          expect_in="root")

    # --- NOEXEC applets (fork, call in child, no exec) ---
    _test("env", "env",
          expect_in="PWD")
    _test("id", "id",
          expect_in="uid=0")
    _test("date", "date",
          expect_in="1969")
    _test("ls /bin", "ls /bin",
          expect_in="busybox.elf")
    _test("ls -la", "ls -la /bin/",
          expect_in="busybox.elf")
    _test("ls /tmp", "ls /tmp",
          expect_in="hello.txt")
    _test("head", "head /tmp/lines.txt",
          expect_in="line1")
    _test("head -n", "head -n 2 /tmp/lines.txt",
          expect_in="line2")
    _test("cut", "cut -d: -f1 /tmp/fruits.txt",
          expect_in="cherry")
    _test("sort", "sort /tmp/fruits.txt",
          expect_in="apple")
    _test("expr", "expr 2 + 3",
          expect_in="5")
    _test("cp", "cp /tmp/hello.txt /tmp/hello_cp.txt; cat /tmp/hello_cp.txt",
          expect_in="hello world")
    _test("mkdir + ls", "mkdir /tmp/testdir; ls /tmp/",
          expect_in="testdir")
    _test("rm + ls", "rm /tmp/lines.txt; ls /tmp/",
          expect_in="hello.txt")

    # --- Regular applets (fork + exec fallback to NOEXEC) ---
    _test("cat", "cat /tmp/hello.txt",
          expect_in="hello world")
    _test("wc", "wc /tmp/lines.txt",
          expect_in="5")
    _test("tail", "tail -n 2 /tmp/fruits.txt",
          expect_in="elderberry")
    _test("grep -F", "grep -F apple /tmp/fruits.txt",
          expect_in="apple")
    _test("cmp (same)", "cmp /tmp/hello.txt /tmp/hello.txt; echo CMP_RC_$?",
          expect_in="CMP_RC_0")
    _test("nl", "nl /tmp/lines.txt",
          expect_in="1")
    _test("od", "od -c /tmp/hello.txt",
          expect_in="h   e   l   l   o")
    _test("rev", "rev /tmp/hello.txt",
          expect_in="dlrow olleh")
    _test("strings", "strings /tmp/hello.txt",
          expect_in="hello world")
    _test("factor", "factor 12",
          expect_in="2 2 3")
    _test("seq", "seq 3",
          expect_in="3")
    _test("du", "du /tmp/",
          expect_in="/tmp/")
    _test("diff --help", "diff --help",
          expect_in="diff")
    _test("uniq --help", "uniq --help",
          expect_in="uniq")

    # --- Summary ---
    total = passed + failed
    print(f"\n{'=' * 50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print(f"{'=' * 50}")
    if failed > 0:
        raise RuntimeError(f"{failed} smoke test(s) failed")
