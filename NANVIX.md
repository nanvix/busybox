# BusyBox Port for Nanvix

> **TL;DR:** This is a port of BusyBox for the Nanvix operating system, providing a
> minimal shell and ~105 Unix utilities. Jump to [Quick Start](#quick-start) to get started.

---

## Overview

This document describes the port of [BusyBox](https://busybox.net/) for the
[Nanvix](https://github.com/nanvix/nanvix) operating system. BusyBox provides a
single statically-linked binary containing many common Unix utilities and a shell
(ash), suitable for use as the user-space environment on Nanvix.

| Property | Value |
|----------|-------|
| **Base Version** | BusyBox 1.37.0.git |
| **Target Platform** | Nanvix (i686) |
| **Build System** | GNU Make (kconfig) |
| **Build Orchestration** | [nanvix-zutil](https://github.com/nanvix/zutils) |
| **Applets Compiled** | ~105 commands (91 unique entry points) |
| **Binary Size** | ~1.9 MB (stripped) |

**What's included:**
- ✅ Cross-compilation support for Nanvix
- ✅ Static busybox binary (`busybox.elf`)
- ✅ ash shell with standalone mode, arithmetic, and internal globbing
- ✅ 30+ NOFORK applets (run in-process without fork)
- ✅ 60+ NOEXEC/regular applets (run in forked child process)
- ✅ Text editors (vi) and search tools (grep, sed)
- ✅ Hash utilities (md5sum, sha256sum, etc.)
- ✅ Exec fallback: regular applets transparently fall back to in-process execution
- ✅ nanvix-zutil integration (`z.sh` / `z.ps1` / `.nanvix/z.py`)
- ✅ CI/CD integration via reusable workflow

**Shell features:**
- Standalone shell mode (applets run in-process or via fork)
- Nofork applets (no fork/exec needed for built-in commands)
- NOEXEC applets (fork only — applet runs in child, no exec)
- Exec fallback for regular applets (exec fails → NOEXEC-style)
- Internal globbing with full POSIX fnmatch support
- Shell arithmetic (`$((...))`)
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

### Using mkimage + ramfs (recommended)

```bash
# Create a system image with procd + memd + busybox
mkimage.elf -o system.img \
  "procd.elf;procd" "memd.elf;memd" "busybox.elf;ash"

# Create a ramfs image with busybox and test files
mkdir -p staging/bin staging/tmp
cp busybox.elf staging/bin/
mkramfs.elf -o ramfs.img staging/

# Start an interactive ash shell with ramfs
nanvixd.elf -bin-dir ./bin -ramfs ramfs.img -- system.img

# Pipe commands to the shell
echo "echo hello" | nanvixd.elf -bin-dir ./bin -ramfs ramfs.img -- system.img
```

### Building Nanvix with fork support

```bash
cd nanvix/
make all DEPLOYMENT_MODE=standalone MACHINE=microvm RELEASE=no FEATURES=fork
make install DEPLOYMENT_MODE=standalone MACHINE=microvm RELEASE=no FEATURES=fork
```

### Interactive Shell

Once booted into ash, all applet categories work:

```
# echo Hello from BusyBox on Nanvix     (shell builtin)
Hello from BusyBox on Nanvix
# basename /usr/local/bin/myapp          (NOFORK)
myapp
# ls /tmp                                (NOEXEC — fork, no exec)
hello.txt  fruits.txt
# cat /tmp/hello.txt                     (regular — fork + exec fallback)
hello world
# sort /tmp/fruits.txt                   (NOEXEC — fork, no exec)
apple
banana
cherry
# grep -F apple /tmp/fruits.txt          (regular — fixed-string grep)
apple
# wc /tmp/hello.txt                      (regular — fork + exec fallback)
      1       2      12 /tmp/hello.txt
# echo $((6 * 7))                        (shell arithmetic)
42
```

---

## Configuration

The BusyBox configuration for Nanvix is stored in `configs/nanvix_defconfig`.

### Enabled Features

| Feature | Description |
|---------|-------------|
| **ash shell** | Interactive shell with editing and history |
| **ASH_INTERNAL_GLOB** | Internal globbing (bypasses missing libc glob) |
| **FEATURE_SH_MATH** | Shell arithmetic support |
| **FEATURE_SH_STANDALONE** | Shell prefers BusyBox applets over external binaries |
| **FEATURE_SH_NOFORK** | Run nofork applets directly (no fork/exec needed) |
| **FEATURE_PREFER_APPLETS** | exec() prefers BusyBox applets |
| **BUSYBOX_EXEC_PATH** | Set to `/bin/busybox.elf` for Nanvix VFS |
| **Static linking** | No shared libraries (required for Nanvix) |

### Enabled Applets (~105 commands)

| Category | Applets |
|----------|---------|
| **Shell** | ash, sh |
| **NOFORK Applets** | arch, basename, clear, dirname, echo, false, fsync, hostid, kill, link, logname, mkdir, nproc, printenv, printf, pwd, readlink, realpath, rmdir, sync, test, [, [[, touch, true, truncate, tty, ttysize, uname, unlink, usleep, which, whoami |
| **Coreutils** | cat, chgrp, chmod, chown, cp, cut, date, dd, du, env, expand, fold, groups, head, id, install, ln, ls, mktemp, mv, nl, od, paste, rev, rm, seq, shred, shuf, sleep, sort, split, stat, strings, stty, tac, tail, tee, timeout, tr, unexpand, uniq, wc, xargs, xxd, yes |
| **Search/Text** | grep, egrep, fgrep, sed, vi |
| **Hash/Crypto** | base64, cksum, md5sum, sha1sum, sha256sum, sha3sum, sha512sum, sum |
| **Math** | expr, factor |
| **Misc** | cal, cmp, comm, diff, dos2unix, find, hd, hexdump, unix2dos |

### Disabled Features

| Feature | Reason |
|---------|--------|
| Networking | Not supported on Nanvix |
| Job control | Requires signals/process groups not fully available |
| `/proc`-dependent applets | killall, killall5, free, ps, top — no /proc filesystem |
| Priority applets | nice, renice — no getpriority/setpriority syscalls |
| FIFO/device creation | mkfifo — mknod returns ENOSYS |
| Filesystem stats | df — no statfs/statvfs syscalls |
| awk | Heavily depends on regex (regcomp/regexec are stubs) |
| Login/password | No user management on Nanvix |
| Init system | Nanvix has its own init |
| Modules/hardware | No kernel module or hardware management |

### Modifying Configuration

```bash
# Start menuconfig (requires ncurses-dev)
make menuconfig

# Save changes to defconfig
make -f Makefile.nanvix CONFIG_NANVIX=y savedefconfig
```

---

## POSIX Compatibility Layer

The file `nanvix_stubs.c` provides stub or replacement implementations for
POSIX functions not available in Nanvix's newlib or libposix:

| Function | Implementation |
|----------|---------------|
| `fnmatch()` | Full POSIX implementation (*, ?, [...], FNM_PATHNAME, FNM_PERIOD) |
| `getpwnam()`, `getpwent()` | Returns static root user entry |
| `getgrnam()`, `getgrgid()`, `getgrent()` | Returns static root group entry |
| `vfork()` | Delegates to `fork()` |
| `clearenv()` | Clears environ array |
| `gethostid()` | Returns 0 |
| `getlogin_r()` | Returns "root" |
| `getgrouplist()` | Returns single group (gid 0) |
| `sync()` | No-op (returns 0) |
| `wait()` | Wraps `waitpid(-1, ...)` |
| `sched_getaffinity()` | Reports 1 CPU |
| `cfget/cfset*speed()` | Returns/ignores baud rate |
| `sigaction()`, `sigprocmask()`, etc. | No-op stubs |

The `include/nanvix-compat/` directory provides compatibility headers:
- `sys/stat.h`: Adds `UTIME_NOW` / `UTIME_OMIT` macros (needed by `touch`)

---

## Changes Summary

### Nanvix-Specific Files

| File | Purpose |
|------|---------|
| `Makefile.nanvix` | Cross-compilation wrapper for Nanvix |
| `nanvix_stubs.c` | Stub/replacement implementations for missing POSIX functions |
| `configs/nanvix_defconfig` | BusyBox configuration for Nanvix (~105 applets enabled) |
| `include/nanvix-compat/` | Compatibility headers for Nanvix's newlib |
| `include/platform.h` | Modified: Nanvix platform detection |
| `Makefile` | Modified: Fix CONFIG_EXTRA_LDLIBS quoting |
| `shell/ash.c` | Modified: Exec fallback — when `execve()` fails, regular applets fall back to NOEXEC-style in-process execution |
| `.nanvix/z.py` | ZScript subclass (build orchestration) |
| `.nanvix/nanvix.toml` | Package manifest |
| `.nanvix/config.py` | Shared configuration constants |
| `.nanvix/build.py` | Build orchestration logic |
| `.nanvix/ramfs.py` | Ramfs image generation and staging |
| `.nanvix/test.py` | Smoke test orchestration (mkimage + ramfs, 45 tests) |
| `NANVIX.md` | This documentation file |
| `z` | Cross-platform entry point |
| `z.sh` | Thin bash wrapper for nanvix-zutil |
| `z.ps1` | Thin PowerShell wrapper for nanvix-zutil |
| `.github/workflows/nanvix-ci.yml` | CI workflow |

---

## Known Limitations

| Limitation | Impact |
|------------|--------|
| **No kernel pipe support** | Pipes between commands (`cmd1 \| cmd2`) do not work |
| **No fcntl F_DUPFD / dup / dup2** | File redirections (`> file`, `< file`) fail |
| **No command substitution** | `$(cmd)` and backticks require pipe support |
| **Kernel heap limits exec** | `execve()` fails for large binaries (kernel heap max alloc = 512 bytes); ash falls back to in-process execution automatically |
| **Lossy argv serialization** | `execve()` serializes argv as space-separated; arguments containing spaces break (e.g., `grep "hello world"`) |
| **No job control** | Background jobs (`&`), Ctrl+Z not supported |
| **No /proc filesystem** | Process-related applets (ps, top, killall) disabled |
| **No networking** | All network applets disabled |
| **Regex stubs** | `regcomp`/`regexec` always return `REG_NOMATCH`; grep/sed regex patterns do not match (use `grep -F` for literal matching) |
| **No user database** | `whoami` returns "unknown uid 0" (libposix getpwuid has no user DB) |
| **Static linking only** | Required by Nanvix |

### Applet Execution Model

| Type | Mechanism | Fork? | Exec? | Status |
|------|-----------|-------|-------|--------|
| **Shell builtin** | Runs inside ash | No | No | ✅ Works |
| **NOFORK** | Runs inside ash process | No | No | ✅ Works |
| **NOEXEC** | Fork child, call applet function | Yes | No | ✅ Works |
| **Regular** | Fork child, exec fails → NOEXEC fallback | Yes | No* | ✅ Works |

\* Regular applets attempt `execve(/bin/busybox.elf)` which fails due to kernel
heap limits. The patched ash automatically falls back to NOEXEC-style in-process
execution in the forked child. This is transparent to the user.

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
