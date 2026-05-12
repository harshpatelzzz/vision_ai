"""System integrity: SHA-256 hashes of models and pipeline source files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _glob_models(root: Path, patterns: List[str]) -> List[Path]:
    out: List[Path] = []
    for pat in patterns:
        out.extend(root.glob(pat))
    return sorted({p for p in out if p.is_file()})


def _collect_python_sources(root: Path, subpackages: List[str]) -> List[Path]:
    files: List[Path] = []
    for sub in subpackages:
        d = root / sub
        if d.is_dir():
            files.extend(p for p in d.rglob("*.py") if p.is_file())
    return sorted(set(files))


def generate_attestation_report(
    project_root: Path,
    model_globs: List[str] | None = None,
    script_globs: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Hash model weights (``.pt``) and key Python modules for integrity reporting.

    Returns a JSON-serializable dict suitable for ``GET /attestation``.
    """
    root = Path(project_root)
    mg = model_globs or ["models/*.pt"]

    models: Dict[str, str] = {}
    for path in _glob_models(root, mg):
        rel = str(path.relative_to(root))
        try:
            models[rel] = _sha256_file(path)
        except OSError:
            models[rel] = "MISSING_OR_UNREADABLE"

    scripts: Dict[str, str] = {}
    if script_globs:
        for pat in script_globs:
            for path in root.glob(pat):
                if path.is_file() and path.suffix == ".py":
                    rel = str(path.relative_to(root))
                    try:
                        scripts[rel] = _sha256_file(path)
                    except OSError:
                        scripts[rel] = "MISSING_OR_UNREADABLE"
    else:
        for path in _collect_python_sources(root, ["core", "scripts", "security", "api"]):
            rel = str(path.relative_to(root))
            try:
                scripts[rel] = _sha256_file(path)
            except OSError:
                scripts[rel] = "MISSING_OR_UNREADABLE"

    return {
        "project_root": str(root.resolve()),
        "algorithm": "SHA-256",
        "models": models,
        "scripts": scripts,
        "summary": {
            "model_count": len(models),
            "script_count": len(scripts),
        },
    }


def attestation_report_json(project_root: Path, **kwargs: Any) -> str:
    """Pretty JSON string for API responses."""
    return json.dumps(generate_attestation_report(project_root, **kwargs), indent=2)
