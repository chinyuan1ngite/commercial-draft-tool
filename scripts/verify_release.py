"""Validate a locally built Windows release archive.

The executable smoke checks run code from the archive. Only use this tool with
artifacts produced from a trusted checkout or trusted CI run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import zipfile


EXE_NAME = "Commercial1688DraftTool.exe"
FORBIDDEN_PARTS = {
    ".local",
    ".venv",
    "config",
    "data",
    "drafts",
    "products",
    "profiles",
    "runtime",
}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class ReleaseValidationError(ValueError):
    """Raised when an archive violates the release contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _normalized_name(info: zipfile.ZipInfo) -> str:
    name = info.filename.replace("\\", "/")
    path = PurePosixPath(name)
    if (
        not name
        or "\x00" in name
        or path.is_absolute()
        or re.match(r"^[A-Za-z]:", name)
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ReleaseValidationError(f"unsafe archive path: {info.filename!r}")
    for part in path.parts:
        stem = part.split(".", 1)[0].upper()
        if (
            any(character in part for character in '<>:"|?*')
            or part.endswith((" ", "."))
            or stem in WINDOWS_RESERVED_NAMES
        ):
            raise ReleaseValidationError(f"unsafe Windows archive path: {info.filename!r}")
    if ((info.external_attr >> 16) & 0o170000) == 0o120000:
        raise ReleaseValidationError(f"symbolic links are not allowed: {info.filename!r}")
    forbidden = FORBIDDEN_PARTS.intersection(part.casefold() for part in path.parts)
    if forbidden:
        raise ReleaseValidationError(f"runtime/private directory in archive: {info.filename!r}")
    return path.as_posix().rstrip("/")


def _inspect(zipped: zipfile.ZipFile, version: str) -> dict[str, zipfile.ZipInfo]:
    corrupt = zipped.testzip()
    if corrupt:
        raise ReleaseValidationError(f"archive CRC failed: {corrupt}")

    entries: dict[str, zipfile.ZipInfo] = {}
    casefolded: dict[str, str] = {}
    for info in zipped.infolist():
        name = _normalized_name(info)
        folded = name.casefold()
        if name in entries or folded in casefolded:
            previous = casefolded.get(folded, name)
            raise ReleaseValidationError(f"duplicate Windows archive path: {previous!r} / {name!r}")
        entries[name] = info
        casefolded[folded] = name

    required = {
        EXE_NAME,
        "VERSION",
        "README.md",
        "CHANGELOG.md",
        "SHA256SUMS.txt",
        "docs/操作说明.md",
        "docs/环境配置.md",
        f"docs/版本说明-{version}.md",
    }
    missing = sorted(required.difference(entries))
    if missing:
        raise ReleaseValidationError(f"required release files missing: {missing}")
    return entries


def _extract(zipped: zipfile.ZipFile, entries: dict[str, zipfile.ZipInfo], target: Path) -> None:
    for name, info in entries.items():
        output = target.joinpath(*PurePosixPath(name).parts)
        if info.is_dir():
            output.mkdir(parents=True, exist_ok=True)
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(zipped.read(info))


def _expected_exe_hash(check_dir: Path) -> str:
    lines = (check_dir / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines()
    pattern = re.compile(rf"^([0-9A-Fa-f]{{64}})\s+\*?{re.escape(EXE_NAME)}$")
    matches = [match.group(1).upper() for line in lines if (match := pattern.match(line.strip()))]
    if len(matches) != 1:
        raise ReleaseValidationError(f"SHA256SUMS.txt must contain one valid entry for {EXE_NAME}")
    return matches[0]


def _run_executable_checks(exe: Path, check_dir: Path, version: str, timeout: int) -> dict[str, object]:
    smoke_runtime = check_dir / "smoke-runtime"
    env = dict(os.environ, DRAFT_TOOL_HOME=str(smoke_runtime))
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    outputs = [(["--smoke-test"], "smoke-result.json"), (["--cli", "--help"], "cli-help.txt")]
    for arguments, filename in outputs:
        capture = check_dir / filename
        env["DRAFT_TOOL_CAPTURE_FILE"] = str(capture)
        try:
            result = subprocess.run(
                [str(exe), *arguments],
                cwd=check_dir,
                env=env,
                capture_output=True,
                timeout=timeout,
                creationflags=creation_flags,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ReleaseValidationError(f"executable check timed out: {arguments}") from exc
        if result.returncode != 0:
            raise ReleaseValidationError(f"executable check failed ({result.returncode}): {arguments}")
        if not capture.is_file():
            raise ReleaseValidationError(f"executable check did not create {filename}")

    try:
        smoke = json.loads((check_dir / "smoke-result.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ReleaseValidationError("smoke-result.json is invalid") from exc
    if smoke.get("version") != version:
        raise ReleaseValidationError(f"executable version mismatch: {smoke.get('version')!r}")
    if Path(smoke.get("runtime", "")).resolve() != smoke_runtime.resolve():
        raise ReleaseValidationError("smoke test used an unexpected runtime directory")
    if "usage:" not in (check_dir / "cli-help.txt").read_text(encoding="utf-8").lower():
        raise ReleaseValidationError("CLI help output is missing usage text")
    return smoke


def validate_release(
    archive: Path,
    version: str,
    *,
    skip_executable_smoke: bool = False,
    timeout: int = 60,
) -> dict[str, object]:
    if not archive.is_file():
        raise ReleaseValidationError(f"archive not found: {archive}")
    with tempfile.TemporaryDirectory(prefix=f"package-check-{version}-") as folder:
        check_dir = Path(folder)
        try:
            with zipfile.ZipFile(archive) as zipped:
                entries = _inspect(zipped, version)
                _extract(zipped, entries, check_dir)
        except zipfile.BadZipFile as exc:
            raise ReleaseValidationError(f"invalid ZIP archive: {archive}") from exc

        packaged_version = (check_dir / "VERSION").read_text(encoding="utf-8-sig").strip()
        if packaged_version != version:
            raise ReleaseValidationError(
                f"VERSION mismatch: expected {version!r}, archive contains {packaged_version!r}"
            )
        exe_hash = _sha256(check_dir / EXE_NAME)
        expected_hash = _expected_exe_hash(check_dir)
        if exe_hash != expected_hash:
            raise ReleaseValidationError("packaged executable SHA256 does not match SHA256SUMS.txt")

        smoke: dict[str, object] | str = "skipped"
        cli_help = "skipped"
        if not skip_executable_smoke:
            smoke = _run_executable_checks(check_dir / EXE_NAME, check_dir, version, timeout)
            cli_help = "passed"

    return {
        "version": version,
        "archive": str(archive.resolve()),
        "bytes": archive.stat().st_size,
        "archive_sha256": _sha256(archive),
        "exe_sha256": exe_hash,
        "package_files": len(entries),
        "crc": "passed",
        "smoke": smoke,
        "cli_help": cli_help,
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--expected-version")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-executable-smoke", action="store_true")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args(argv)

    version = args.expected_version or (root / "VERSION").read_text(encoding="utf-8-sig").strip()
    archive = args.archive or root / "dist" / f"Commercial1688DraftTool-{version}-win64.zip"
    output = args.output or root / ".local" / f"package-verification-{version}.json"
    try:
        summary = validate_release(
            archive.resolve(),
            version,
            skip_executable_smoke=args.skip_executable_smoke,
            timeout=args.timeout,
        )
    except (OSError, UnicodeError, ReleaseValidationError) as exc:
        print(f"Release verification failed: {exc}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
