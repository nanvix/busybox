# BusyBox Port for Nanvix

> **TL;DR:** This is a port of BusyBox for the Nanvix operating system, providing a
> minimal shell and ~105 Unix utilities. Jump to [Quick Start](#quick-start) to
> build, or [Running an Interactive Shell](#running-an-interactive-shell) to try it.

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
- ✅ vfsd integration for fork-aware file descriptor tracking
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

# 4. Test (runs 45 smoke tests)
./z test
```

### Building Against a Local Nanvix Checkout

If you have a local Nanvix build (e.g. at `~/src/nanvix/nanvix`), use
`--with-nanvix` to overlay its binaries into the sysroot:

```bash
# Setup once — resolves sysroot and overlays local binaries
./z setup --with-nanvix ~/src/nanvix/nanvix

# Or set the environment variable
export WITH_NANVIX=~/src/nanvix/nanvix
./z setup
./z build
./z test
```

The overlay copies `nanvixd.elf`, `kernel.elf`, `mkramfs.elf`, `linuxd.elf`,
`uservm.elf`, `vfsd.elf`, `libposix.a`, and `user.ld` from the local build.

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

This section explains how to reproduce running an ash shell on Nanvix, step by
step. There are two approaches: the automated way using `./z test`, and the
manual way using mkimage + ramfs directly.

### Prerequisites

You need a working Nanvix build with fork support and a compiled `busybox.elf`.

**Build Nanvix** (if not already built):

```bash
cd ~/src/nanvix/nanvix
make all DEPLOYMENT_MODE=standalone MACHINE=microvm
```

**Build BusyBox** (if not already built):

```bash
cd ~/src/nanvix/usr/bin/busybox
./z setup --with-nanvix ~/src/nanvix/nanvix
./z build
```

After both builds, you should have:

| Binary | Location |
|--------|----------|
| `nanvixd.elf` | `~/src/nanvix/nanvix/bin/nanvixd.elf` |
| `kernel.elf` | `~/src/nanvix/nanvix/bin/kernel.elf` |
| `mkimage.elf` | `~/src/nanvix/nanvix/bin/mkimage.elf` |
| `mkramfs.elf` | `~/src/nanvix/nanvix/bin/mkramfs.elf` |
| `procd.elf` | `~/src/nanvix/nanvix/bin/procd.elf` |
| `memd.elf` | `~/src/nanvix/nanvix/bin/memd.elf` |
| `vfsd.elf` | `~/src/nanvix/nanvix/bin/vfsd.elf` |
| `busybox.elf` | `~/src/nanvix/usr/bin/busybox/busybox.elf` |

### Running an Interactive Shell (Manual)

All commands below run from the **Nanvix root directory** (where `bin/` lives):

```bash
cd ~/src/nanvix/nanvix
```

Set a shorthand for the BusyBox binary path:

```bash
BUSYBOX=~/src/nanvix/usr/bin/busybox/busybox.elf
```

#### Step 1: Create a System Image

A system image bundles the daemons and the shell into one bootable payload.
The format is `"binary_path;process_name"` pairs passed to `mkimage`:

```bash
# Recommended: include vfsd for fork-aware FD tracking
./bin/mkimage.elf -o system.img \
  "./bin/procd.elf;procd" \
  "./bin/memd.elf;memd" \
  "./bin/vfsd.elf;vfsd" \
  "$BUSYBOX;ash"
```

> **Note:** `procd` must be listed first (it is the init process), followed by
> `memd`, then optional daemons like `vfsd`, and finally the user program (`ash`).
> You can omit the `vfsd.elf` line for a minimal image (fork still works, but
> without FD tracking).

#### Step 2: Create a Ramfs Image

The ramfs image provides the filesystem visible to the guest. Place the busybox
binary at `/bin/busybox.elf` so that ash can find and exec applets:

```bash
mkdir -p staging/bin staging/tmp

# Copy busybox binary
cp "$BUSYBOX" staging/bin/busybox.elf

# Optional: add test fixture files
echo "hello world" > staging/tmp/hello.txt
printf "cherry\napple\nbanana\n" > staging/tmp/fruits.txt

# Create the ramfs image
./bin/mkramfs.elf -o ramfs.img staging/
```

#### Step 3: Boot the Shell

```bash
# Interactive mode — type commands at the "# " prompt
./bin/nanvixd.elf -bin-dir ./bin -ramfs ramfs.img -- system.img

# Pipe mode — pipe commands to stdin (useful for scripting/testing)
echo "echo hello; ls /bin" | ./bin/nanvixd.elf -bin-dir ./bin -ramfs ramfs.img -- system.img
```

The `-bin-dir` flag tells nanvixd where to find `kernel.elf`. The `--` separates
nanvixd flags from the system image path.

#### Step 4: Try Some Commands

```
# echo Hello from BusyBox on Nanvix     (shell builtin)
Hello from BusyBox on Nanvix
# basename /usr/local/bin/myapp          (NOFORK — no fork needed)
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
# seq 5                                  (regular — sequence generator)
1
2
3
4
5
# echo $((6 * 7))                        (shell arithmetic)
42
# uname                                  (NOFORK — OS name)
nanvix
```

> **Tip:** nanvixd does not exit when stdin reaches EOF — interactive sessions
> and piped commands will time out after the guest finishes. This is expected
> behavior. The test harness handles this with a 15-second timeout.

### All-in-One: `./z test`

The simplest way to validate the full stack — run from the **BusyBox directory**:

```bash
cd ~/src/nanvix/usr/bin/busybox

# Build BusyBox and run all 45 smoke tests
./z setup --with-nanvix ~/src/nanvix/nanvix
./z build
./z test
```

This automatically:
1. Creates a system image with `procd + memd + vfsd + ash`
2. Creates a ramfs with busybox and test fixture files
3. Runs 45 smoke tests across all applet categories
4. Reports pass/fail results

---

## Architecture

### System Image Layout

The system image contains a multi-binary initrd. On boot, `nanvixd` loads the
kernel, which then starts each binary in order:

```
┌─────────────────────────────────────────────┐
│  System Image (created by mkimage)          │
│                                             │
│  1. procd.elf  — process manager daemon     │
│  2. memd.elf   — memory manager daemon      │
│  3. vfsd.elf   — virtual filesystem daemon  │
│  4. ash (busybox.elf) — user shell          │
└─────────────────────────────────────────────┘
```

### Daemon Roles

| Daemon | Role |
|--------|------|
| **procd** | Process lifecycle: fork, exec, waitpid, exit. Manages the process table and coordinates fork notifications to registered resource servers. |
| **memd** | Memory management: page allocation, virtual memory. |
| **vfsd** | Virtual filesystem daemon: receives fork notifications from procd and tracks child→parent relationships for file descriptor management. |

### Fork Flow (Suspended Fork)

When ash runs a NOEXEC or regular applet, it calls `fork()`. The fork flow is:

```
ash (parent)
  │
  ├── 1. fork() → sends ForkRequest to procd
  │
  ├── procd receives ForkRequest
  │     ├── 2. Calls kernel fork_process_suspended(parent_pid)
  │     │     └── Kernel creates child with deep-copied address space
  │     │         but does NOT place it on the ready queue (suspended)
  │     │
  │     ├── 3. Notifies registered servers (vfsd) via ForkNotify message
  │     │     └── vfsd records child→parent mapping, responds OK
  │     │
  │     ├── 4. Calls kernel resume_forked_process(child_pid)
  │     │     └── Kernel moves child from fork_pending → ready queue
  │     │
  │     └── 5. Sends ForkResponse(child_pid) to parent
  │
  ├── Parent: receives child_pid, continues
  │
  └── Child: wakes up, runs applet function, exits
```

The suspended fork mechanism ensures that resource servers (like vfsd) are
notified and have completed their bookkeeping **before** the child process
starts executing. This prevents IPC message stream contamination.

### Applet Execution Model

| Type | Mechanism | Fork? | Exec? | Status |
|------|-----------|-------|-------|--------|
| **Shell builtin** | Runs inside ash | No | No | ✅ Works |
| **NOFORK** | Runs inside ash process | No | No | ✅ Works |
| **NOEXEC** | Fork child, call applet function | Yes | No | ✅ Works |
| **Regular** | Fork child, exec fails → NOEXEC fallback | Yes | No* | ✅ Works |

\* Regular applets attempt `execve(/bin/busybox.elf)` which fails due to kernel
heap limits. The patched ash (`shell/ash.c`) automatically falls back to
NOEXEC-style in-process execution in the forked child. This is transparent to
the user.

### VFS File Descriptors

- VFS FDs start at 1024 (`VFS_FD_BASE` in `config/src/fds.rs`).
- FDs 0–2 are kernel console (IKC — inter-kernel communication).
- The VFS library (`src/libs/vfs/`) uses a global static `FD_TABLE` with 64 slots.
- After `fork()` with `deep_clone_vmem`, the child inherits an independent copy
  of the entire VFS state (including the FD table) via memory cloning.
- `vfsd` tracks fork relationships so that future per-FD operations can be
  coordinated across parent and child.

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

## Test Suite

The smoke test suite (`.nanvix/test.py`) runs 45 tests across all applet
categories. Each test pipes a shell command to ash and checks the output.

### Running Tests

```bash
# Automated (recommended)
./z test

# Or manually specify the Nanvix build
WITH_NANVIX=~/src/nanvix/nanvix ./z test
```

### Test Categories

| Category | Count | Examples |
|----------|-------|---------|
| Shell builtins | 9 | echo, printf, true/false, variables, arithmetic, test |
| NOFORK applets | 8 | basename, dirname, nproc, realpath, uname, usleep, logname |
| NOEXEC applets | 14 | env, id, date, ls, head, cut, sort, expr, cp, mkdir, rm |
| Regular applets | 14 | cat, wc, tail, grep -F, cmp, nl, od, rev, strings, factor, seq, du, diff, uniq |

### Expected Output

```
  PASS: Test 1: echo
  PASS: Test 2: printf
  ...
  PASS: Test 44: diff --help
  PASS: Test 45: uniq --help

==================================================
Results: 45/45 passed, 0 failed
==================================================
```

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
| `.nanvix/z.py` | ZScript subclass (build orchestration, local Nanvix overlay) |
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

---

## Troubleshooting

### `vfsd.elf not found` Warning

If vfsd.elf is not found in the sysroot, the test system builds the system image
without it. Fork still works, but without FD tracking. To fix:

```bash
# Rebuild Nanvix (vfsd is built automatically)
cd nanvix/ && make all DEPLOYMENT_MODE=standalone MACHINE=microvm

# Re-overlay
./z setup --with-nanvix ~/src/nanvix/nanvix
```

### Test Timeouts

Each test has a 15-second timeout. If nanvixd hangs, check:
- Is `kernel.elf` in the bin directory? (`-bin-dir` flag)
- Is the system image valid? (rebuild with `mkimage.elf`)
- Does the Nanvix build have fork support enabled?

### Build Fails with Missing `libposix.a`

Run `./z setup` to download the sysroot, or point to a local Nanvix build:

```bash
./z setup --with-nanvix ~/src/nanvix/nanvix
```

The setup resolves `libposix.a` from `sysroot-debug/lib/` or `sysroot-release/lib/`.

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
