# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Nanvix build orchestration for BusyBox."""

from __future__ import annotations

import dataclasses
from pathlib import Path, PurePosixPath

import _test

from nanvix_zutil import (
    TOOLCHAIN_CONTAINER_PATH,
    DockerConfig,
    ZScript,
    run,
)
from nanvix_zutil.paths import bin_out, out_dir, repo_root, test_out


class BusyBoxBuild(ZScript):
    """Build BusyBox with the pinned Nanvix C SDK."""

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
            str((bin_out() / "busybox.elf").relative_to(root)),
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
            f"BIN_OUT={translate(bin_out())}",
            f"TEST_OUT={translate(test_out())}",
            *targets,
        ]

    def setup(self) -> bool:
        """Download the Nanvix runtime sysroot."""
        return super().setup()

    def build(self) -> None:
        """Cross-compile and stage busybox.elf."""
        run(*self._make_args("all"), cwd=repo_root(), docker=self.docker)

    def test(self) -> None:
        """Run every selected host and Nanvix test phase."""
        _test.BusyBoxTests(self).run(self.targets)

    def clean(self) -> None:
        """Remove BusyBox and zutils build outputs."""
        run(*self._make_args("clean"), cwd=repo_root(), docker=self.docker)


if __name__ == "__main__":
    BusyBoxBuild.main()
