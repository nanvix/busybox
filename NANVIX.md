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

## Runtime Notes

BusyBox is installed as `/bin/busybox` in test ramfs images. Ash prefers
in-process BusyBox applets. If Nanvix cannot re-exec the multicall binary, the
Nanvix-only ash fallback runs the selected applet from the forked address
space; non-Nanvix behavior remains unchanged.

Current kernel constraints relevant to BusyBox are:

- pipelines are not yet reliable enough for the upstream shell test harness;
- symbolic and hard links return `ENOTSUP`;
- `/proc`, mount tables, and filesystem-stat interfaces are unavailable;
- dynamic linking is unsupported.

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
