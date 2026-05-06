# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Nanvix build script for BusyBox.

Usage:
    ./z setup      # Download Nanvix sysroot
    ./z build      # Cross-compile busybox.elf
    ./z test       # Run smoke tests (echo, ash)
    ./z clean      # Remove build artifacts
    ./z distclean  # Deep clean (build artifacts + untracked files)

Options:
    --with-nanvix PATH  Use local Nanvix binaries from PATH.
"""

import os
import shutil
import sys
from pathlib import Path

from nanvix_zutil import (
    CFG_SYSROOT,
    CFG_TOOLCHAIN,
    EXIT_MISSING_DEP,
    ZScript,
    log,
)

import sys as _sys

_sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_sibling

build_mod = load_sibling("build", __file__)
config = load_sibling("config", __file__)
test_mod = load_sibling("test", __file__)

# Config key for persisting the --with-nanvix path.
_CFG_LOCAL_NANVIX = "local_nanvix_path"

# Early --with-nanvix extraction via environment variable.
_EARLY_LOCAL_NANVIX: str | None = os.environ.get("NANVIX_LOCAL_PATH") or None


class BusyBoxBuild(ZScript):
    """Build script for nanvix/busybox."""

    _local_nanvix_path: str | None = None

    @classmethod
    def main(cls, *, repo_root: Path | None = None) -> None:
        """Pre-parse ``--with-nanvix`` and delegate to ZScript.main()."""
        if _EARLY_LOCAL_NANVIX is not None:
            cls._local_nanvix_path = _EARLY_LOCAL_NANVIX
        super().main(repo_root=repo_root)

    # ---- Local Nanvix overlay --------------------------------------------

    def _overlay_local_nanvix(self) -> None:
        """Copy local Nanvix binaries into the sysroot."""
        nanvix_path = self._local_nanvix_path or self.config.get(
            _CFG_LOCAL_NANVIX, ""
        )
        if not nanvix_path:
            return

        nanvix_path = os.path.abspath(os.path.expanduser(nanvix_path))
        if not os.path.isdir(nanvix_path):
            log.warning(f"--with-nanvix path no longer exists: {nanvix_path}")
            return

        if self.config.get(_CFG_LOCAL_NANVIX, "") != nanvix_path:
            self.config.set(_CFG_LOCAL_NANVIX, nanvix_path)
            self.config.save()

        sysroot = self.config.get(CFG_SYSROOT, "")
        if not sysroot:
            return

        nanvix_dir = Path(nanvix_path)
        sysroot_path = Path(sysroot)

        log.info(f"Overlaying local Nanvix binaries from {nanvix_dir}")

        bin_src = nanvix_dir / "bin"
        bin_dst = sysroot_path / "bin"
        bin_dst.mkdir(parents=True, exist_ok=True)

        binaries = [
            "nanvixd.elf",
            "kernel.elf",
            "mkramfs.elf",
            "linuxd.elf",
            "uservm.elf",
        ]

        for name in binaries:
            src = bin_src / name
            if src.is_file():
                shutil.copy2(src, bin_dst / name)
                log.info(f"  Copied {name}")

        lib_dst = sysroot_path / "lib"
        lib_dst.mkdir(parents=True, exist_ok=True)
        lib_src = nanvix_dir / "lib"

        if lib_src.is_dir():
            for lib_name in ["libposix.a"]:
                src = lib_src / lib_name
                if src.is_file():
                    shutil.copy2(src, lib_dst / lib_name)
                    log.info(f"  Copied {lib_name}")

        # Linker script
        user_ld_candidates = [
            nanvix_dir / "lib" / "user.ld",
            nanvix_dir / "sysroot-release" / "lib" / "user.ld",
            nanvix_dir / "build" / "user" / "linker" / "x86" / "user.ld",
        ]
        for candidate in user_ld_candidates:
            if candidate.is_file():
                shutil.copy2(candidate, lib_dst / "user.ld")
                log.info(f"  Copied user.ld from {candidate}")
                break

    # ---- Common helpers --------------------------------------------------

    def _get_host_paths(self) -> tuple[str, str]:
        """Return (sysroot, toolchain) from config."""
        sysroot = self.config.get(CFG_SYSROOT, "")
        if not sysroot:
            log.fatal(
                f"{CFG_SYSROOT} is not set.",
                code=EXIT_MISSING_DEP,
                hint="Run `./z setup` first to download the sysroot.",
            )
        toolchain = self.config.get(
            CFG_TOOLCHAIN, config.TOOLCHAIN_DEFAULT_PATH
        )
        return sysroot, toolchain or config.TOOLCHAIN_DEFAULT_PATH

    def _build_kwargs(self) -> dict[str, object]:
        """Return common keyword arguments for build/test modules."""
        return {
            "platform": self.config.machine,
            "process_mode": self.config.deployment_mode,
            "memory_size": self.config.memory_size,
        }

    # ---- Commands --------------------------------------------------------

    def setup(self) -> bool:
        """Download the Nanvix sysroot."""
        local_nanvix = self._local_nanvix_path
        if local_nanvix:
            local_nanvix = os.path.abspath(os.path.expanduser(local_nanvix))

        used_fallback = False
        if local_nanvix and os.path.isdir(local_nanvix):
            self._setup_from_local_nanvix(local_nanvix)
        else:
            used_fallback = super().setup()

        self.config.save()
        self._overlay_local_nanvix()
        return used_fallback

    def _setup_from_local_nanvix(self, local_path: str) -> None:
        """Configure sysroot from a local Nanvix build directory."""
        self.config.set(_CFG_LOCAL_NANVIX, local_path)
        # Use the local path as sysroot if no other sysroot configured
        sysroot = self.config.get(CFG_SYSROOT, "")
        if not sysroot:
            self.config.set(CFG_SYSROOT, local_path)

    def build(self) -> None:
        """Cross-compile busybox.elf for Nanvix."""
        self._overlay_local_nanvix()
        sysroot, toolchain = self._get_host_paths()
        build_mod.build(
            sysroot,
            toolchain,
            self.repo_root,
            **self._build_kwargs(),
            run_fn=lambda *args, **kw: self.run(*args, **kw),
            docker=self.docker is not None,
        )

    def test(self) -> None:
        """Run BusyBox smoke tests on Nanvix."""
        self._overlay_local_nanvix()
        sysroot, toolchain = self._get_host_paths()
        test_mod.run_all(
            sysroot,
            toolchain,
            self.repo_root,
            **self._build_kwargs(),
            run_fn=lambda *args, **kw: self.run(*args, **kw),
            docker=self.docker is not None,
        )

    def clean(self) -> None:
        """Remove build artifacts."""
        build_mod.clean(self.repo_root)

    def distclean(self) -> None:
        """Deep clean: all build artifacts and untracked files."""
        build_mod.distclean(self.repo_root)


if __name__ == "__main__":
    BusyBoxBuild.main()
