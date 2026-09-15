#!/usr/bin/env python3
"""Installe les fichiers de routage Claude de ce dépôt sans écraser les données utilisateur."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


SOURCE = Path(__file__).resolve().parent
START = "<!-- claudeskills:routing:start -->"
END = "<!-- claudeskills:routing:end -->"


class InstallError(Exception):
    pass


@dataclass
class Action:
    path: Path
    content: bytes
    status: str


def _decode(data: bytes, path: Path) -> tuple[str, bool]:
    bom = data.startswith(b"\xef\xbb\xbf")
    try:
        return data.decode("utf-8-sig"), bom
    except UnicodeDecodeError as exc:
        raise InstallError(f"{path}: UTF-8 invalide") from exc


def _encode(text: str, bom: bool) -> bytes:
    data = text.encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if bom else data


def _parse_json(data: bytes, path: Path) -> dict:
    text, _ = _decode(data, path)
    try:
        tree = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InstallError(f"{path}: JSON invalide: {exc}") from exc
    if not isinstance(tree, dict):
        raise InstallError(f"{path}: un objet JSON était attendu")
    return tree


def _merge_tree(source: dict, target: dict, path: Path, prefix: str = "") -> tuple[dict, bool, list[str]]:
    merged = dict(target)
    changed = False
    warnings: list[str] = []
    for key, value in source.items():
        dotted = f"{prefix}{key}"
        if key not in target:
            merged[key] = value
            changed = True
        elif isinstance(value, dict) and isinstance(target[key], dict):
            sub, sub_changed, sub_warnings = _merge_tree(value, target[key], path, f"{dotted}.")
            merged[key] = sub
            changed = changed or sub_changed
            warnings.extend(sub_warnings)
        elif target[key] != value:
            warnings.append(f"{path}: {dotted} conservé ({target[key]!r}, valeur proposée {value!r})")
    return merged, changed, warnings


def _merge_settings(source: bytes, target: bytes, path: Path) -> tuple[bytes, list[str]]:
    source_tree = _parse_json(source, SOURCE / ".claude/settings.json")
    target_tree = _parse_json(target, path)
    target_text, bom = _decode(target, path)
    merged, changed, warnings = _merge_tree(source_tree, target_tree, path)
    if not changed:
        return target, warnings
    newline = "\r\n" if "\r\n" in target_text else "\n"
    text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    return _encode(text.replace("\n", newline) if newline != "\n" else text, bom), warnings


def _merge_instructions(source: bytes, target: bytes, path: Path) -> tuple[bytes, list[str]]:
    source_text, _ = _decode(source, SOURCE / "CLAUDE.md")
    target_text, bom = _decode(target, path)
    newline = "\r\n" if "\r\n" in target_text else "\n"
    block = source_text.replace("\r\n", "\n").rstrip("\n").replace("\n", newline)
    if START in target_text or END in target_text:
        if START not in target_text or END not in target_text:
            raise InstallError(f"{path}: marqueurs claudeskills incomplets")
        if f"{START}{newline}{block}{newline}{END}" in target_text:
            return target, []
        return target, [f"{path}: bloc claudeskills existant conservé car il diffère de la source"]
    separator = "" if not target_text else (newline if target_text.endswith(("\n", "\r")) else newline * 2)
    merged = f"{target_text}{separator}{START}{newline}{block}{newline}{END}{newline}"
    return _encode(merged, bom), []


def _managed_sources() -> list[Path]:
    return [
        *sorted((SOURCE / ".claude/agents").glob("*.md")),
        SOURCE / ".claude/skills/quota-orchestrator/SKILL.md",
    ]


def _unsafe(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(os.path, "isjunction", lambda _: False)(path))


def _check_path(target: Path, path: Path) -> None:
    current = target
    if _unsafe(current):
        raise InstallError(f"{current}: symlink/junction refusé")
    parts = path.relative_to(target).parts
    for index, part in enumerate(parts):
        current /= part
        if current.exists() and _unsafe(current):
            raise InstallError(f"{current}: symlink/junction refusé")
        if current.exists() and index < len(parts) - 1 and not current.is_dir():
            raise InstallError(f"{current}: un répertoire était attendu")


def plan(target: Path) -> tuple[list[Action], list[tuple[str, Path]], list[str]]:
    if not target.exists() or not target.is_dir():
        raise InstallError(f"{target}: la cible doit être un répertoire existant")
    target = target.resolve()
    if target == SOURCE:
        raise InstallError(f"{target}: la cible est le dépôt source ; indiquez le projet à équiper")
    actions: list[Action] = []
    unchanged: list[tuple[str, Path]] = []
    warnings: list[str] = []

    instructions_target = target / "CLAUDE.md"
    _check_path(target, instructions_target)
    source_instructions = (SOURCE / "CLAUDE.md").read_bytes()
    if instructions_target.exists():
        if not instructions_target.is_file():
            raise InstallError(f"{instructions_target}: un fichier était attendu")
        original = instructions_target.read_bytes()
        merged, notes = _merge_instructions(source_instructions, original, instructions_target)
        warnings.extend(notes)
        if merged != original:
            actions.append(Action(instructions_target, merged, "fusionné"))
        else:
            unchanged.append(("déjà présent", instructions_target))
    else:
        managed, _ = _merge_instructions(source_instructions, b"", instructions_target)
        actions.append(Action(instructions_target, managed, "créé"))

    source_settings_path = SOURCE / ".claude/settings.json"
    source_settings = source_settings_path.read_bytes()
    _parse_json(source_settings, source_settings_path)
    settings_target = target / ".claude/settings.json"
    _check_path(target, settings_target)
    if settings_target.exists():
        if not settings_target.is_file():
            raise InstallError(f"{settings_target}: un fichier était attendu")
        original = settings_target.read_bytes()
        merged, notes = _merge_settings(source_settings, original, settings_target)
        warnings.extend(notes)
        if merged != original:
            actions.append(Action(settings_target, merged, "fusionné"))
        else:
            unchanged.append(("déjà présent", settings_target))
    else:
        actions.append(Action(settings_target, source_settings, "créé"))

    for source in _managed_sources():
        destination = target / source.relative_to(SOURCE)
        _check_path(target, destination)
        if destination.exists():
            if not destination.is_file():
                raise InstallError(f"{destination}: un fichier était attendu")
            if destination.read_bytes() == source.read_bytes():
                unchanged.append(("déjà présent", destination))
            else:
                unchanged.append(("préservé avec avertissement", destination))
                warnings.append(f"{destination}: fichier divergent conservé")
        else:
            actions.append(Action(destination, source.read_bytes(), "créé"))
    return actions, unchanged, warnings


def _write(path: Path, content: bytes, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not replace:
        with path.open("xb") as stream:
            stream.write(content)
        return
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
        shutil.copymode(path, temporary)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def apply(target: Path, actions: list[Action]) -> Path | None:
    changed = [action for action in actions if action.path.exists()]
    backup = None
    if changed:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = target / ".claudeskills-backup" / stamp
        for action in changed:
            saved = backup / action.path.relative_to(target)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(action.path, saved)

    created: list[Path] = []
    created_dirs: set[Path] = set()
    try:
        for action in actions:
            existed = action.path.exists()
            parent = action.path.parent
            while not parent.exists() and parent != target:
                created_dirs.add(parent)
                parent = parent.parent
            _write(action.path, action.content, existed)
            if not existed:
                created.append(action.path)
        for action in actions:
            if action.path.suffix == ".json":
                _parse_json(action.path.read_bytes(), action.path)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        for path in sorted(created_dirs, key=lambda item: len(item.parts), reverse=True):
            try:
                path.rmdir()
            except OSError:
                pass
        if backup:
            for action in changed:
                shutil.copy2(backup / action.path.relative_to(target), action.path)
        raise
    return backup


def install(target: Path, dry_run: bool = False) -> int:
    if _unsafe(target):
        raise InstallError(f"{target}: symlink/junction refusé")
    target = target.resolve()
    actions, unchanged, warnings = plan(target)
    backup = None if dry_run else apply(target, actions)
    prefix = "[dry-run] " if dry_run else ""
    for action in actions:
        print(f"{prefix}{action.status}: {action.path.relative_to(target)}")
    for status, path in unchanged:
        print(f"{status}: {path.relative_to(target)}")
    for warning in warnings:
        print(f"avertissement: {warning}", file=sys.stderr)
    if dry_run and any(action.path.exists() for action in actions):
        print("[dry-run] sauvegarde: .claudeskills-backup/<horodatage>/")
    if backup:
        print(f"sauvegarde: {backup.relative_to(target)}")
    print(f"résumé: {len(actions)} changement(s), {len(unchanged)} fichier(s) conservé(s), {len(warnings)} avertissement(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", type=Path, default=Path.cwd(), help="répertoire du projet (défaut: courant)")
    parser.add_argument("--dry-run", action="store_true", help="afficher le plan sans écrire")
    args = parser.parse_args()
    try:
        return install(args.target, args.dry_run)
    except (InstallError, OSError) as exc:
        print(f"erreur: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
