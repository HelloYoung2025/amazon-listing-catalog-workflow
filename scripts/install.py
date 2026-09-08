#!/usr/bin/env python3
"""Install all three Amazon skills; existing installations require --replace."""
from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

from check_package import NAMES, ROOT, verify


def install(destination: Path, replace: bool = False) -> Path | None:
    errors = verify(ROOT / "skills")
    if errors:
        raise ValueError("Incomplete source package:\n" + "\n".join(errors))
    destination = destination.expanduser().resolve()
    if destination.exists() and not destination.is_dir():
        raise ValueError("Destination must be a Skill root directory")
    targets = {name: destination / name for name in NAMES}
    if any(path.is_symlink() for path in targets.values()):
        raise ValueError("Refusing symlinked target; resolve its ownership before installing")
    if any(ROOT.is_relative_to(path) for path in targets.values()):
        raise ValueError("Clone the repository outside the installed Skill directories first")
    existing = {name: path for name, path in targets.items() if path.exists()}
    if existing and not replace:
        raise ValueError("Nothing changed. Existing targets require --replace (with backup): "
                         + ", ".join(existing))
    destination.mkdir(parents=True, exist_ok=True)
    backup = None
    saved, installed = [], []
    with tempfile.TemporaryDirectory(prefix="amazon-skills-stage-", dir=destination.parent) as temp:
        stage = Path(temp)
        for name in NAMES:
            shutil.copytree(ROOT / "skills" / name, stage / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        errors = verify(stage)
        if errors:
            raise ValueError("Staged package failed verification:\n" + "\n".join(errors))
        if existing:
            backup = Path(tempfile.mkdtemp(prefix="amazon-skills-backup-", dir=destination.parent))
            print(f"Backup destination before replacement: {backup}", flush=True)
        try:
            for name, path in existing.items():
                path.rename(backup / name)
                saved.append(name)
            for name in NAMES:
                (stage / name).rename(targets[name])
                installed.append(name)
            errors = verify(destination)
            if errors:
                raise ValueError("Installed package failed verification:\n" + "\n".join(errors))
        except BaseException:
            # Restore only the three exact targets. Preserve all unrelated skills.
            for name in reversed(installed):
                targets[name].rename(stage / name)
            for name in saved:
                (backup / name).rename(targets[name])
            raise
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "skills")
    parser.add_argument("--replace", action="store_true", help="Back up and replace ONLY the three named skills")
    args = parser.parse_args()
    try:
        backup = install(args.dest, args.replace)
    except (OSError, ValueError) as exc:
        print(f"Installation stopped: {exc}")
        return 1
    print(f"Installed and verified all 3 skills at {args.dest.expanduser().resolve()}")
    if backup:
        print(f"Previous directories preserved at: {backup}")
    print("Skills are available on your next turn; use a new task if the client has not refreshed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
