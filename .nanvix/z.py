# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""Nanvix build orchestration for BusyBox.

Lifecycle implementations are split across ``src/``, one mixin per
module:

  - src/config.py  ConfigMixin — shared sysroot manifest, docker output
                   plumbing, and the ``make`` argument constructor.
  - src/test.py    TestMixin — ``./z test`` phases.

``BusyBoxBuild`` composes the mixins and owns the trivial ``build`` /
``clean`` hooks directly.
"""

from __future__ import annotations

from nanvix_zutil import run
from nanvix_zutil.paths import repo_root

from src.test import TestMixin


class BusyBoxBuild(TestMixin):
    """Build BusyBox with the pinned Nanvix C SDK."""

    def build(self) -> None:
        """Cross-compile and stage busybox.elf."""
        run(*self._make_args("all"), cwd=repo_root(), docker=self.docker)

    def clean(self) -> None:
        """Remove BusyBox and zutils build outputs."""
        run(*self._make_args("clean"), cwd=repo_root(), docker=self.docker)


if __name__ == "__main__":
    BusyBoxBuild.main()

# See nanvix-python's z.py: hide the partial mixin bases so that
# `discover_script_class()` picks `BusyBoxBuild` from `vars(module)`.
# TODO: https://github.com/nanvix/zutils/issues/269
del TestMixin
