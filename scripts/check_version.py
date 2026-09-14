"""Check that every declared project version is identical."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys
import tomllib


def _module_version(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == "__version__" for target in targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, str):
                raise ValueError(f"{path}: __version__ must be a string")
            values.append(value)
    if len(values) != 1:
        raise ValueError(f"{path}: expected exactly one __version__ assignment")
    return values[0]


def declared_versions(root: Path) -> dict[str, str]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return {
        "VERSION": (root / "VERSION").read_text(encoding="utf-8-sig").strip(),
        "pyproject.toml": pyproject["project"]["version"],
        "draft_tool.__version__": _module_version(root / "src" / "draft_tool" / "__init__.py"),
    }


def check_versions(root: Path) -> str:
    versions = declared_versions(root)
    unique = set(versions.values())
    if len(unique) != 1 or not next(iter(unique), ""):
        details = ", ".join(f"{name}={value!r}" for name, value in versions.items())
        raise ValueError(f"version declarations do not match: {details}")
    return next(iter(unique))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        version = check_versions(args.root.resolve())
    except (FileNotFoundError, KeyError, SyntaxError, ValueError) as exc:
        print(f"Version check failed: {exc}", file=sys.stderr)
        return 1
    print(f"Version consistency passed: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
