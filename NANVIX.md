# BusyBox Port for Nanvix

> **TL;DR:** This is a port of BusyBox for the Nanvix operating system, providing a
> minimal shell and Unix utilities. Jump to [Quick Start](#quick-start) to get started.

---

## Overview

This document describes the port of [BusyBox](https://busybox.net/) for the
[Nanvix](https://github.com/nanvix/nanvix) operating system. BusyBox provides a
single statically-linked binary containing many common Unix utilities and a shell
(ash), suitable for use as the user-space environment on Nanvix.

| Property | Value |
|----------|-------|
| **Base Version** | BusyBox 1.36.1 |
| **Target Platform** | Nanvix (i686) |
| **Build System** | GNU Make (kconfig) |
| **Build Orchestration** | [nanvix-zutil](https://github.com/nanvix/zutils) |

**What's included:**
- ✅ Cross-compilation support for Nanvix
- ✅ Static busybox binary (`busybox.elf`)
- ✅ ash shell with nofork applet support
- ✅ Basic coreutils (cat, ls, echo, mkdir, rm, etc.)
- ✅ nanvix-zutil integration (`z.sh` / `z.ps1` / `.nanvix/z.py`)
- ✅ CI/CD integration via reusable workflow

**Shell features:**
- Standalone shell mode (applets run in-process)
- Nofork applets (no fork/exec needed for built-in commands)
- Command line editing and history
- Bash compatibility mode

---

## Quick Start

```bash
# 1. Install nanvix-zutil
pip install nanvix-zutil

# 2. Setup (downloads Nanvix sysroot)
./z setup

# 3. Build
./z build

# 4. Test
./z test
```

### Manual Build (without nanvix-zutil)

```bash
# 1. Pull the Docker image
docker pull nanvix/toolchain:latest-minimal

# 2. Download Nanvix sysroot
curl -fsSL https://raw.githubusercontent.com/nanvix/nanvix/refs/heads/dev/scripts/get-nanvix.sh \
  | bash -s -- nanvix-artifacts
tar -xjf nanvix-artifacts/*microvm*standalone*.tar.bz2 -C nanvix-artifacts
export NANVIX_HOME=$(find nanvix-artifacts -maxdepth 2 -type d -name "bin" -exec dirname {} \; | head -1)

# 3. Build (Docker is used automatically if native toolchain not found)
make -f Makefile.nanvix CONFIG_NANVIX=y NANVIX_HOME="$NANVIX_HOME"
```

---

## Running on Nanvix

### Running BusyBox Applets

```bash
# Run a single applet
nanvixd.elf -bin-dir ./bin -ramfs busybox-ramfs.img \
  -- ./bin/busybox.elf "echo Hello from BusyBox on Nanvix!"

# Start an interactive ash shell
nanvixd.elf -bin-dir ./bin -ramfs busybox-ramfs.img \
  -- ./bin/busybox.elf "ash"
```

### Interactive Shell

Once booted into ash, built-in commands and nofork applets work directly:

```
/ $ echo Hello
Hello
/ $ pwd
/
/ $ ls /bin
busybox.elf  cat          echo         ls           sh
/ $ cat /proc/version    # if available
```

---

## Configuration

The BusyBox configuration for Nanvix is stored in `configs/nanvix_defconfig`.
This is a minimal configuration optimized for Nanvix's capabilities:

### Enabled Features

| Feature | Description |
|---------|-------------|
| **ash shell** | Interactive shell with editing and history |
| **FEATURE_SH_STANDALONE** | Shell prefers BusyBox applets over external binaries |
| **FEATURE_SH_NOFORK** | Run nofork applets directly (no fork/exec needed) |
| **FEATURE_PREFER_APPLETS** | exec() prefers BusyBox applets |
| **Static linking** | No shared libraries (required for Nanvix) |

### Enabled Applets

| Category | Applets |
|----------|---------|
| **Shell** | ash |
| **Coreutils** | basename, cat, date, dd, echo, false, head, ls, mkdir, mv, printf, pwd, rm, rmdir, sleep, tail, test, touch, tr, true, uname, wc, yes |
| **Text** | vi |

### Disabled Features

| Feature | Reason |
|---------|--------|
| Networking | Not supported on Nanvix |
| Job control | Requires signals/process groups not fully available |
| Process utilities | ps, kill, top depend on /proc |
| Login/password | No user management on Nanvix |
| Init system | Nanvix has its own init |

### Modifying Configuration

```bash
# Start menuconfig (requires ncurses-dev)
make menuconfig

# Save changes to defconfig
make -f Makefile.nanvix CONFIG_NANVIX=y savedefconfig
```

---

## Changes Summary

### Nanvix-Specific Files

| File | Purpose |
|------|---------|
| `Makefile.nanvix` | Cross-compilation wrapper for Nanvix |
| `nanvix_stubs.c` | Stub implementations for missing POSIX functions |
| `configs/nanvix_defconfig` | BusyBox configuration for Nanvix |
| `include/nanvix-compat/` | Compatibility headers for Nanvix's newlib |
| `include/platform.h` | Modified: Nanvix platform detection |
| `Makefile` | Modified: Fix CONFIG_EXTRA_LDLIBS quoting |
| `.nanvix/z.py` | ZScript subclass (build orchestration) |
| `.nanvix/nanvix.toml` | Package manifest |
| `.nanvix/config.py` | Shared configuration constants |
| `.nanvix/build.py` | Build orchestration logic |
| `.nanvix/ramfs.py` | Ramfs image generation |
| `.nanvix/test.py` | Smoke test orchestration |
| `NANVIX.md` | This documentation file |
| `z` | Cross-platform entry point |
| `z.sh` | Thin bash wrapper for nanvix-zutil |
| `z.ps1` | Thin PowerShell wrapper for nanvix-zutil |
| `.github/workflows/nanvix-ci.yml` | CI workflow |

---

## Known Limitations

| Limitation | Impact |
|------------|--------|
| **No fork for external commands** | In standalone mode, only nofork applets and builtins work in-process |
| **No job control** | Background jobs (`&`), Ctrl+Z not supported |
| **No pipelines** | Pipes between commands require fork (limited in standalone) |
| **No command substitution** | `$(cmd)` and backticks require fork |
| **No /proc filesystem** | Process-related applets (ps, top) disabled |
| **No networking** | All network applets disabled |
| **Static linking only** | Required by Nanvix |

---

## CI/CD

The GitHub Actions workflow at `.github/workflows/nanvix-ci.yml` invokes the
reusable Nanvix CI workflow at `nanvix/workflows/.github/workflows/nanvix-ci.yml@v1.14.0`.

### Build Matrix

| Platform | Process Mode | Memory |
|----------|--------------|--------|
| microvm | standalone | 128 MB |
| microvm | single-process | 128 MB |
| microvm | multi-process | 128 MB |

---
