# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Shared state for the busybox ZScript.

Holds the sysroot manifest, docker output plumbing, and the ``make``
argument constructor. Lifecycle mixins inherit from :class:`ConfigMixin`
so ``self.<helper>`` calls type-check without any ``Protocol`` plumbing.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path, PurePosixPath

from nanvix_zutil import (
    TOOLCHAIN_CONTAINER_PATH,
    DockerConfig,
    ZScript,
)
from nanvix_zutil.paths import out_dir, regular_out, repo_root, test_out

__all__ = ("ConfigMixin",)


class ConfigMixin(ZScript):
    """Shared state + helpers for busybox lifecycle mixins."""

    # The SDK owns libc and user.ld; the downloaded sysroot is runtime-only.
    SYSROOT_REQUIRED_FILES = (
        "bin/nanvixd.elf",
        "bin/kernel.elf",
        "bin/mkramfs.elf",
    )
    SYSROOT_REQUIRED_FILES_WINDOWS = (
        "bin/nanvixd.exe",
        "bin/kernel.elf",
        "bin/mkramfs.exe",
    )

    def docker_config(self, image: str) -> DockerConfig:
        """Copy generated artifacts back from Docker Desktop builds."""
        config = super().docker_config(image)
        root = repo_root()
        output_files = [
            "busybox",
            "busybox.elf",
            "busybox.links",
            ".config",
            str((out_dir() / "bin" / "busybox.elf").relative_to(root)),
            str((regular_out() / "bin" / "busybox.elf").relative_to(root)),
            str((test_out() / "busybox.elf").relative_to(root)),
            str((test_out() / "busybox.links").relative_to(root)),
            str((test_out() / "busybox.config").relative_to(root)),
        ]
        return dataclasses.replace(config, output_files=output_files)

    def _make_args(self, *targets: str) -> list[str]:
        def translate(path: Path) -> PurePosixPath | Path:
            return self.docker.translate_path(path) if self.docker else path

        return [
            "make",
            "-f",
            ".nanvix/Makefile.nanvix",
            f"NANVIX_TOOLCHAIN={TOOLCHAIN_CONTAINER_PATH}",
            f"OUT_DIR={translate(out_dir())}",
            f"BIN_OUT={translate(regular_out() / 'bin')}",
            f"TEST_OUT={translate(test_out())}",
            *targets,
        ]
