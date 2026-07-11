# Copyright(c) The Maintainers of Nanvix.
# Licensed under the MIT License.

"""BusyBox artifact, unit, and target integration tests."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import struct
import sys
import tempfile
from pathlib import Path

from nanvix_zutil import CFG_SYSROOT, ZScript, log
from nanvix_zutil.exitcodes import EXIT_TEST_FAILURE
from nanvix_zutil.helpers import InitRdArgs, make_initrd, run
from nanvix_zutil.paths import repo_root, test_out

_ALL_PHASES = ("test-smoke", "test-unit", "test-integration")
_UNSUPPORTED_SHELL = re.compile(r"(?<!\|)\|(?!\|)|\$\(|`")
_UNSUPPORTED_LINK = re.compile(
    r"(^|[;&\s])(?:busybox\s+)?ln(?:\s|$)|\b(?:hard|soft|sym)links?\b",
    re.MULTILINE,
)
_SMOKE_CASES = (
    ("echo", "echo NANVIX_ECHO_OK_7X", "NANVIX_ECHO_OK_7X"),
    ("printf", "printf 'FMT_%s_%s\\n' ALPHA BETA", "FMT_ALPHA_BETA"),
    ("true", "true; echo TRUE_RC_$?", "TRUE_RC_0"),
    ("false", "false; echo FALSE_RC_$?", "FALSE_RC_1"),
    ("shell variable", "MYVAR=UNIQUE_VAL_93; echo $MYVAR", "UNIQUE_VAL_93"),
    ("shell arithmetic", "echo MATH_$((17 * 3))", "MATH_51"),
    (
        "test file",
        "test -f /nonexistent || echo TEST_FILE_OK_22",
        "TEST_FILE_OK_22",
    ),
    ("test string", "test abc = abc && echo TEST_STRING_OK_55", "TEST_STRING_OK_55"),
    ("test nonempty", "test -n hello && echo TEST_N_OK_88", "TEST_N_OK_88"),
    ("basename", "basename /usr/local/bin/myapp.txt", "myapp.txt"),
    ("dirname", "dirname /usr/local/bin/myapp.txt", "/usr/local/bin"),
    ("nproc", "nproc", "1"),
    ("realpath", "realpath /bin/../bin/busybox", "/bin/busybox"),
    ("uname", "uname", "nanvix"),
    ("usleep", "usleep 1000; echo USLEEP_OK_44", "USLEEP_OK_44"),
    ("logname", "logname", "root"),
    ("env", "NANVIX_ENV_MARKER=OK env", "NANVIX_ENV_MARKER=OK"),
    ("env command", "env echo ENV_EXEC_OK", "ENV_EXEC_OK"),
    ("id", "id", "uid=0"),
    ("date", "date", "UTC"),
    ("ls bin", "ls /bin", "busybox"),
    ("ls long", "ls -la /bin", "busybox"),
    ("ls tmp", "ls /tmp", "hello.txt"),
    ("head", "head /tmp/lines.txt", "line1"),
    ("head count", "head -n 2 /tmp/lines.txt", "line2"),
    ("cut", "cut -d: -f1 /tmp/fruits.txt", "cherry"),
    ("sort", "sort /tmp/fruits.txt", "apple"),
    ("expr", "expr 2 + 3", "5"),
    (
        "cp",
        "cp /tmp/hello.txt /tmp/hello-copy.txt; cat /tmp/hello-copy.txt",
        "hello world",
    ),
    ("mkdir", "mkdir /tmp/testdir; ls /tmp", "testdir"),
    (
        "rm",
        "rm /tmp/lines.txt; test ! -f /tmp/lines.txt && echo RM_OK_31",
        "RM_OK_31",
    ),
    ("cat", "cat /tmp/hello.txt", "hello world"),
    ("wc", "wc /tmp/lines.txt", "5"),
    ("tail", "tail -n 2 /tmp/fruits.txt", "elderberry"),
    ("grep fixed", "grep -F apple /tmp/fruits.txt", "apple"),
    (
        "cmp",
        "cmp /tmp/hello.txt /tmp/hello.txt; echo CMP_RC_$?",
        "CMP_RC_0",
    ),
    ("nl", "nl /tmp/lines.txt", "1"),
    ("od", "od -c /tmp/hello.txt", "h   e   l   l   o"),
    ("rev", "rev /tmp/hello.txt", "dlrow olleh"),
    ("strings", "strings /tmp/hello.txt", "hello world"),
    ("factor", "factor 12", "2 2 3"),
    ("seq", "seq 3", "3"),
    ("timeout command", "timeout 2 echo TIMEOUT_EXEC_OK", "TIMEOUT_EXEC_OK"),
    (
        "xargs command",
        "echo input > /tmp/xargs.in; xargs echo XARGS_EXEC_OK < /tmp/xargs.in",
        "XARGS_EXEC_OK input",
    ),
    (
        "find exec",
        "find /fixtures -name hello.txt -exec echo FIND_EXEC_OK \\;",
        "FIND_EXEC_OK",
    ),
    ("du", "du /tmp", "/tmp"),
    ("diff help", "diff --help", "diff"),
    ("uniq help", "uniq --help", "uniq"),
)


class BusyBoxTests:
    """Run host-side checks and tests inside Nanvix."""

    def __init__(self, script: ZScript) -> None:
        self.script = script

    def run(self, targets: list[str]) -> None:
        """Run all phases, or the phases named after ``--``."""
        phases = list(targets) if targets else list(_ALL_PHASES)
        if "test-all" in phases:
            phases = list(_ALL_PHASES)

        unknown = sorted(set(phases) - set(_ALL_PHASES))
        if unknown:
            log.fatal(
                f"Unknown test phase(s): {', '.join(unknown)}",
                code=EXIT_TEST_FAILURE,
                hint=f"Choose from: {', '.join(_ALL_PHASES)}",
            )

        for phase in phases:
            getattr(self, phase.replace("-", "_"))()

    def _binary(self) -> Path:
        binary = test_out() / "busybox.elf"
        if not binary.is_file():
            log.fatal(
                f"{binary} not found.",
                code=EXIT_TEST_FAILURE,
                hint="Run './z build' first.",
            )
        return binary

    def _sysroot(self) -> Path:
        configured = self.script.config.get(CFG_SYSROOT, "")
        if not configured:
            log.fatal(
                "Nanvix sysroot is not configured.",
                code=EXIT_TEST_FAILURE,
                hint="Run './z setup --with-docker IMAGE' first.",
            )
        return Path(str(configured))

    @staticmethod
    def _host_tool(sysroot: Path, name: str) -> Path:
        suffix = ".exe" if sys.platform == "win32" else ".elf"
        return sysroot / "bin" / f"{name}{suffix}"

    def test_smoke(self) -> None:
        """Validate the target artifact and maximal test configuration."""
        log.info("=== BusyBox smoke tests ===")
        binary = self._binary()
        image = binary.read_bytes()
        if image[:6] != b"\x7fELF\x01\x01":
            log.fatal(
                f"{binary} is not a 32-bit little-endian ELF file.",
                code=EXIT_TEST_FAILURE,
            )
        if len(image) < 52 or struct.unpack_from("<H", image, 18)[0] != 3:
            log.fatal(
                f"{binary} does not target i386.",
                code=EXIT_TEST_FAILURE,
            )

        phoff = struct.unpack_from("<I", image, 28)[0]
        phentsize = struct.unpack_from("<H", image, 42)[0]
        phnum = struct.unpack_from("<H", image, 44)[0]
        for index in range(phnum):
            offset = phoff + index * phentsize
            if (
                offset + 4 <= len(image)
                and struct.unpack_from("<I", image, offset)[0] == 3
            ):
                log.fatal(
                    f"{binary} contains a dynamic interpreter.",
                    code=EXIT_TEST_FAILURE,
                )

        config = (test_out() / "busybox.config").read_text(encoding="utf-8")
        required = (
            "CONFIG_BUSYBOX=y",
            "CONFIG_STATIC=y",
            "CONFIG_UNIT_TEST=y",
            "CONFIG_ASH=y",
            "CONFIG_FEATURE_SH_STANDALONE=y",
        )
        missing = [entry for entry in required if entry not in config]
        if missing:
            log.fatal(
                f"Required configuration missing: {', '.join(missing)}",
                code=EXIT_TEST_FAILURE,
            )

        links = {
            line.strip()
            for line in (test_out() / "busybox.links")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        }
        if len(links) < 100:
            log.fatal(
                f"Only {len(links)} applet links were built; expected at least 100.",
                code=EXIT_TEST_FAILURE,
            )
        log.success(f"PASS: static i386 ELF with {len(links)} applet links")

    def _run_guest(
        self,
        initrd: Path,
        *,
        ramfs: Path | None = None,
        timeout: int = 180,
    ) -> None:
        sysroot = self._sysroot()
        command = [
            str(self._host_tool(sysroot, "nanvixd")),
            "-bin-dir",
            str(sysroot / "bin"),
        ]
        if ramfs is not None:
            command.extend(["-ramfs", str(ramfs)])
        command.extend(["--", str(initrd)])
        run(*command, cwd=test_out(), timeout=timeout)

    def test_unit(self) -> None:
        """Run every CONFIG_UNIT_TEST test in the Nanvix guest."""
        log.info("=== BusyBox unit tests on Nanvix ===")
        initrd = make_initrd(
            self.script,
            self._binary(),
            test_out(),
            args=InitRdArgs(app_args=["unit"]),
        )
        try:
            self._run_guest(initrd)
        finally:
            initrd.unlink(missing_ok=True)
        log.success("PASS: BusyBox unit tests")

    def test_integration(self) -> None:
        """Run BusyBox's upstream testsuite against the Nanvix binary."""
        log.info("=== BusyBox upstream testsuite on Nanvix ===")
        binary = self._binary()
        sysroot = self._sysroot()

        with tempfile.TemporaryDirectory(prefix="nanvix_busybox_") as temporary:
            temporary_path = Path(temporary)
            ramfs_root = temporary_path / "ramfs"
            bin_dir = ramfs_root / "bin"
            bin_dir.mkdir(parents=True)

            staged_binary = bin_dir / "busybox"
            shutil.copy2(binary, staged_binary)
            os.link(staged_binary, bin_dir / "busybox.elf")
            os.link(staged_binary, ramfs_root / "busybox")
            dev_dir = ramfs_root / "dev"
            dev_dir.mkdir()
            (dev_dir / "null").write_bytes(b"")
            fixtures = ramfs_root / "fixtures"
            fixtures.mkdir()
            (fixtures / "hello.txt").write_text(
                "hello world\n", encoding="ascii", newline="\n"
            )
            (fixtures / "fruits.txt").write_text(
                "cherry\napple\nbanana\ndate\nelderberry\n",
                encoding="ascii",
                newline="\n",
            )
            (fixtures / "lines.txt").write_text(
                "line1\nline2\nline3\nline4\nline5\n",
                encoding="ascii",
                newline="\n",
            )
            config_path = test_out() / "busybox.config"
            shutil.copy2(config_path, bin_dir / ".config")

            applets = ["busybox"]
            for entry in (
                (test_out() / "busybox.links").read_text(encoding="utf-8").splitlines()
            ):
                relative = entry.strip().lstrip("/")
                if not relative:
                    continue
                applets.append(Path(relative).name)

            option_flags = [
                line.split("=", 1)[0].removeprefix("CONFIG_")
                for line in config_path.read_text(encoding="utf-8").splitlines()
                if line.startswith("CONFIG_")
            ]
            suite = ramfs_root / "testsuite"
            shutil.copytree(repo_root() / "testsuite", suite)
            testing = suite / "testing.sh"
            testing_source = testing.read_text(encoding="utf-8")
            pipe_command = '  $ECHO -ne "$5" | eval "$2" > actual\n'
            if pipe_command not in testing_source:
                log.fatal(
                    "BusyBox testing.sh no longer has the expected stdin pipeline.",
                    code=EXIT_TEST_FAILURE,
                )
            testing_source = testing_source.replace(
                pipe_command,
                '  $ECHO -ne "$5" > standard_input\n'
                '  ( eval "$2" < standard_input ) > actual\n',
                1,
            ).replace(
                "  rm -f input expected actual\n",
                "  rm -f input expected actual standard_input\n",
                1,
            )
            testing.write_text(testing_source, encoding="utf-8", newline="\n")

            # Nanvix does not yet support reliable shell pipelines or command
            # substitution. Keep every upstream test file that needs neither.
            test_applets: list[str] = []
            testcases: list[Path] = []
            new_testcases: list[Path] = []
            for applet in sorted(set(applets)):
                new_style = suite / f"{applet}.tests"
                if new_style.is_file():
                    source = new_style.read_text(encoding="utf-8")
                    sourced_files = re.findall(
                        r"^\.\s+\./([^\s]+)", source, re.MULTILINE
                    )
                    unsupported_source = any(
                        dependency != "testing.sh"
                        and (repo_root() / "testsuite" / dependency).is_file()
                        and _UNSUPPORTED_SHELL.search(
                            (repo_root() / "testsuite" / dependency).read_text(
                                encoding="utf-8"
                            )
                        )
                        for dependency in sourced_files
                    )
                    unsupported = (
                        _UNSUPPORTED_SHELL.search(source)
                        or unsupported_source
                        or _UNSUPPORTED_LINK.search(source)
                        or "/dev/zero" in source
                        or "/dev/full" in source
                    )
                    if unsupported:
                        new_style.unlink()
                    else:
                        test_applets.append(applet)
                        new_testcases.append(new_style)

                old_style = suite / applet
                if not old_style.is_dir():
                    continue
                for testcase in old_style.iterdir():
                    if not testcase.is_file():
                        continue
                    source = testcase.read_text(encoding="utf-8")
                    required_features = [
                        feature.removeprefix("CONFIG_")
                        for line in source.splitlines()
                        if line.startswith("# FEATURE: ")
                        for feature in line.removeprefix("# FEATURE: ").split()
                    ]
                    unsupported = (
                        _UNSUPPORTED_SHELL.search(source)
                        or _UNSUPPORTED_LINK.search(source)
                        or "/dev/zero" in source
                        or "/dev/full" in source
                        or any(
                            feature not in option_flags for feature in required_features
                        )
                    )
                    if unsupported:
                        testcase.unlink()
                compatible = [path for path in old_style.iterdir() if path.is_file()]
                if compatible:
                    test_applets.append(applet)
                    testcases.extend(sorted(compatible))

            if not testcases and not new_testcases:
                log.fatal(
                    "No pipe-free BusyBox tests were staged.",
                    code=EXIT_TEST_FAILURE,
                )

            for testcase in [*testcases, *new_testcases]:
                testcase.write_text(
                    testcase.read_text(encoding="utf-8"),
                    encoding="utf-8",
                    newline="\n",
                )

            runner = suite / "nanvix-runtest"
            script = [
                "#!/bin/sh",
                "cd /testsuite || exit 1",
                "export PATH=/bin",
                "export ECHO=echo",
                "export bindir=/bin",
                "export srcdir=/testsuite",
                "export SKIP_INTERNET_TESTS=1",
                f"export OPTIONFLAGS=':{':'.join(option_flags)}:'",
                "failed=0",
                "number=0",
                "run_smoke() {",
                '  name="$1"',
                '  command="$2"',
                '  expected="$3"',
                "  rm -rf /tmp/testdir /tmp/hello-copy.txt",
                "  rm -f /tmp/hello.txt /tmp/fruits.txt /tmp/lines.txt",
                "  cp /fixtures/hello.txt /tmp/hello.txt",
                "  cp /fixtures/fruits.txt /tmp/fruits.txt",
                "  cp /fixtures/lines.txt /tmp/lines.txt",
                "  : > /dev/null",
                '  eval "$command" > /tmp/smoke-actual 2>&1',
                '  if grep -F "$expected" /tmp/smoke-actual > /dev/null 2>&1; then',
                '    echo "PASS: smoke $name"',
                "  else",
                '    echo "FAIL: smoke $name"',
                "    cat /tmp/smoke-actual",
                "    failed=$((failed + 1))",
                "  fi",
                "}",
                "run_test() {",
                '  testcase="$1"',
                '  name="${testcase##*/}"',
                "  number=$((number + 1))",
                '  work="/testsuite/.tmpdir-$number"',
                '  rm -rf "$work"',
                '  mkdir "$work" || exit 1',
                '  cd "$work" || exit 1',
                "  : > /dev/null",
                "  d=/testsuite",
                "  export d",
                '  if ash "$testcase"; then',
                '    echo "PASS: $name"',
                "  else",
                '    echo "FAIL: $name"',
                "    failed=$((failed + 1))",
                "  fi",
                "  cd /testsuite || exit 1",
                '  rm -rf "$work"',
                "}",
                "run_new_test() {",
                '  testcase="$1"',
                '  name="${testcase##*/}"',
                "  cd /testsuite || exit 1",
                "  : > /dev/null",
                '  if ash "$testcase"; then',
                '    echo "PASS: suite $name"',
                "  else",
                '    echo "FAIL: suite $name"',
                "    failed=$((failed + 1))",
                "  fi",
                "}",
            ]
            for name, command, expected in _SMOKE_CASES:
                script.append(
                    "run_smoke "
                    f"{shlex.quote(name)} "
                    f"{shlex.quote(command)} "
                    f"{shlex.quote(expected)}"
                )
            for testcase in testcases:
                relative = testcase.relative_to(ramfs_root)
                script.append(f"run_test '/{relative.as_posix()}'")
            for testcase in new_testcases:
                relative = testcase.relative_to(ramfs_root)
                script.append(f"run_new_test '/{relative.as_posix()}'")
            script.extend(
                [
                    'echo "Nanvix BusyBox tests: '
                    f"{len(_SMOKE_CASES)} smoke, {len(testcases)} legacy, "
                    f'{len(new_testcases)} suites, $failed failed"',
                    'test "$failed" -eq 0',
                ]
            )
            runner.write_text("\n".join(script) + "\n", encoding="ascii", newline="\n")
            (ramfs_root / "tmp").mkdir()

            ramfs = temporary_path / "busybox-tests.img"
            run(
                str(self._host_tool(sysroot, "mkramfs")),
                "-o",
                str(ramfs),
                str(ramfs_root),
            )

            initrd = make_initrd(
                self.script,
                binary,
                test_out(),
                args=InitRdArgs(app_args=["ash", "/testsuite/nanvix-runtest"]),
            )
            try:
                self._run_guest(initrd, ramfs=ramfs, timeout=600)
            finally:
                initrd.unlink(missing_ok=True)
        log.success(
            f"PASS: {len(_SMOKE_CASES)} applet smoke tests and "
            f"{len(testcases)} legacy tests plus {len(new_testcases)} "
            f"new-style suites for "
            f"{len(set(test_applets))} applets"
        )
