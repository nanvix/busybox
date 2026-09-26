# BusyBox for Nanvix

This branch ports BusyBox 1.36.1 to Nanvix as a statically linked i686 ELF
binary. It uses [nanvix/zutils](https://github.com/nanvix/zutils) for build
orchestration and the Clang-based [nanvix/sdk](https://github.com/nanvix/sdk)
as its only target toolchain.

| Component | Pinned version |
| --- | --- |
| BusyBox | 1.36.1 |
| nanvix-zutil | v0.14.0 |
| Nanvix runtime | v0.19.17 |
| Nanvix C SDK | v0.19.17-sdk.2 |
| Target | `i686-unknown-nanvix` |
| Deployment | microvm, standalone |

## Build

Docker and Python 3.12 or newer are required. The `z` wrapper creates an
isolated Python environment and installs the pinned zutils release
automatically.

```sh
SDK=ghcr.io/nanvix/nanvix-sdk-c-clang:v0.19.17-sdk.2

./z setup --with-docker "$SDK"
./z build
```

`setup` downloads the matching Nanvix runtime sysroot. `build` runs BusyBox's
Kbuild inside the SDK image and produces:

- `busybox.elf`
- `.nanvix/out/release/bin/busybox.elf`
- `.nanvix/out/test/{busybox.elf,busybox.links,busybox.config}`

To use runtime artifacts from a local Nanvix checkout:

```sh
./z setup --with-docker "$SDK" --with-nanvix /path/to/nanvix
```

The build is driven by `.nanvix/Makefile.nanvix`. It selects the SDK's
`clang`, `ld.lld`, and LLVM binutils, and verifies that
`/opt/nanvix/nanvix-sdk.json` exists before compiling. The resulting ELF has
no dynamic interpreter.

## Tests

Run every test phase:

```sh
./z test
```

Or select phases explicitly:

```sh
./z test -- test-smoke
./z test -- test-unit
./z test -- test-integration
```

The enabled coverage is:

| Phase | Coverage |
| --- | --- |
| `test-smoke` | ELF class, architecture, static linkage, mandatory Kconfig options, and the complete generated applet-link set |
| `test-unit` | Every unit test compiled by `CONFIG_UNIT_TEST`, executed inside Nanvix |
| `test-integration` | 48 applet/shell smoke tests plus every runnable BusyBox upstream test (currently 34 legacy cases and 15 new-style suites) |

Integration tests build a ramfs, create a standalone initrd with `procd`,
`memd`, `vfsd`, and BusyBox, then execute it with `nanvixd`.

The harness automatically excludes upstream cases that cannot run correctly on
the current Nanvix kernel:

- shell pipelines and command substitution;
- symlink or hard-link operations;
- `/dev/full` and `/dev/zero` device semantics;
- tests for disabled Kconfig features.

This keeps all currently runnable upstream tests enabled without converting
kernel limitations into false BusyBox failures.

## Configuration

`configs/nanvix_defconfig` enables:

- static linking and the BusyBox multicall applet;
- ash with standalone and nofork applet execution;
- BusyBox's unit-test applet;
- 105 applet links covering core file, text, checksum, shell, editor, search,
  and utility commands.

The configuration intentionally excludes applets requiring unsupported or
inapplicable facilities such as `/proc`, mount/statfs, kernel modules, PAM,
SELinux, init/login management, and hardware administration.

Nanvix's SDK libc now provides the POSIX declarations and implementations used
by this port directly. No local libc stubs or shadow compatibility headers are
linked into BusyBox.

## Known Issues

The port contains the following workarounds for current Nanvix, SDK, and CI
limitations:

| Issue | Workaround |
| --- | --- |
| Re-executing `/bin/busybox` may fail after `fork()` | The Nanvix-only path in `shell/ash.c` runs the selected applet from the cloned address space. Non-Nanvix behavior is unchanged. |
| Applets such as `env`, `timeout`, `xargs`, and `find -exec` launch secondary commands through `BB_EXECVP()` | The Nanvix path in `libbb/executable.c` falls back to in-process applet dispatch when BusyBox self-exec fails. |
| BusyBox assumes mount tables, `statfs`, `wait3`, `/dev/fd`, Ethernet headers, and `%m` printf support | `include/platform.h` disables those capability assumptions for `__nanvix__` and uses the SDK's endian and byte-swap headers. |
| Kconfig string quoting can pass `CONFIG_EXTRA_LDLIBS=""` to `scripts/trylink` as a library name | The top-level `Makefile` removes Kconfig quotes before invoking `trylink`. |
| zutils traditionally expects `libposix.a` and `user.ld` in the downloaded sysroot | The Nanvix SDK now owns libc and the linker script, so `.nanvix/z.py` treats the downloaded sysroot as runtime-only and verifies only runtime binaries. |
| Shell pipelines and command substitution are not reliable enough for the upstream test harness | The staged test harness replaces its stdin pipeline with temporary-file redirection and a subshell, preserving the original isolation semantics. Tests that inherently require pipelines or command substitution are excluded. |
| Symbolic and hard links return `ENOTSUP`; `/dev/full` and `/dev/zero` semantics are unavailable | Tests requiring those facilities are excluded. Ramfs images rely on ash standalone dispatch instead of applet symlinks and use the native `/dev/null` device. |
| GitHub artifact transfer excludes hidden files, and Windows checkouts may use CRLF line endings | The target configuration is staged as `busybox.config`, explicitly included with `busybox.links`, and generated or selected shell scripts are normalized to LF before ramfs creation. |
| Nanvix SDK `v0.19.17-sdk.1` installed `/opt/nanvix/bin` with root-only directory permissions | The port pins `v0.19.17-sdk.2`, which contains the upstream non-root permission fix required by zutils and CI. |
| Nanvix supports only static ELF executables | `configs/nanvix_defconfig` enables static linking and disables shared or individual BusyBox builds. |

These workarounds should be removed when the corresponding Nanvix facilities
or upstream build interfaces become available.

## CI

`.github/workflows/nanvix-ci.yml` uses the shared Nanvix workflow and runs the
full build/test lifecycle for microvm standalone images with 128 MiB and
256 MiB of memory. Windows runtime tests are enabled; cross-compilation still
uses the same pinned SDK container.

## Other Commands

```sh
./z clean
./z release
./z install --output /path/to/destination
```
