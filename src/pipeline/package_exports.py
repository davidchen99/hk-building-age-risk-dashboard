from __future__ import annotations

import zipfile
from pathlib import Path

from src.utils.config import EXPORT_PACKAGE_ZIP, EXPORTS_DIR, FIGURES_DIR, REPORTS_DIR, ensure_dirs

PACKAGE_ROOTS = (
    (EXPORTS_DIR, "exports"),
    (FIGURES_DIR, "figures"),
    (REPORTS_DIR, "reports"),
)


def _archive_name(path: Path) -> str:
    for root, prefix in PACKAGE_ROOTS:
        try:
            relative = path.relative_to(root)
            return str(Path(prefix) / relative).replace("\\", "/")
        except ValueError:
            continue
    return path.name


def iter_export_package_files() -> list[Path]:
    files: list[Path] = []
    package_path = EXPORT_PACKAGE_ZIP.resolve()
    for root, _ in PACKAGE_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.resolve() == package_path:
                continue
            if root == EXPORTS_DIR and path.suffix.lower() == ".zip":
                continue
            files.append(path)
    return files


def create_export_package_zip(output_path: Path | None = None) -> Path:
    ensure_dirs()
    output = output_path or EXPORT_PACKAGE_ZIP
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in iter_export_package_files():
            archive.write(path, _archive_name(path))
    return output
