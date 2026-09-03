"""Build the Windows installer for Fiducia Facture.

Run from the project root with: python scripts\build_release.py
"""
from __future__ import annotations

import ast
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

print("Fiducia Facture Windows release builder starting...", flush=True)
ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def get_version() -> str:
    """Read APP_VERSION from the project version module robustly."""
    candidates = [ROOT / "app" / "version.py", ROOT / "version.py"]
    version_path = next((p for p in candidates if p.is_file()), None)
    if version_path is None:
        matches = sorted(ROOT.rglob("version.py"))
        if len(matches) == 1:
            version_path = matches[0]
    if version_path is None:
        raise SystemExit(
            "Could not find version.py. Expected app\\version.py. "
            f"Project root is: {ROOT}"
        )

    try:
        tree = ast.parse(version_path.read_text(encoding="utf-8-sig"), filename=str(version_path))
    except Exception as exc:
        raise SystemExit(f"Could not read/parse {version_path}: {exc}") from exc

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "APP_VERSION":
                    try:
                        value = ast.literal_eval(node.value)
                    except Exception as exc:
                        raise SystemExit(f"APP_VERSION in {version_path} is not a literal string: {exc}") from exc
                    if isinstance(value, str) and value.strip():
                        print(f"Version source: {version_path}", flush=True)
                        return value.strip()
    raise SystemExit(f"APP_VERSION is missing or invalid in {version_path}")


def main() -> None:
    print(f"Project: {ROOT}", flush=True)
    python = os.environ.get("PYTHON") or sys.executable
    version = get_version()
    print(f"Version: {version}", flush=True)

    run([python, "-m", "pip", "install", "-r", "requirements.txt"])
    run([python, "-m", "pip", "install", "--upgrade", "pyinstaller"])

    shutil.rmtree(BUILD / "pyinstaller", ignore_errors=True)
    shutil.rmtree(DIST, ignore_errors=True)

    run([python, "-m", "PyInstaller", str(BUILD / "FiduciaFacture.spec"), "--clean", "--noconfirm"])

    iscc = os.environ.get("ISCC")
    if not iscc:
        candidates = [
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
        ]
        iscc_path = next((p for p in candidates if p.exists()), None)
        if iscc_path is None:
            raise SystemExit("Inno Setup 6 est introuvable. Installez Inno Setup 6 ou définissez ISCC vers ISCC.exe.")
        iscc = str(iscc_path)

    iss = ROOT / "installer" / "FiduciaFacture.iss"
    run([iscc, f"/DMyAppVersion={version}", str(iss)])

    installers = sorted((DIST / "installer").glob("*.exe"), key=lambda p: p.stat().st_mtime)
    if not installers:
        raise SystemExit("Installer introuvable après compilation Inno Setup")
    installer = installers[-1]
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    sidecar = installer.with_suffix(installer.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {installer.name}\n", encoding="utf-8")
    print(f"\nBUILD SUCCESSFUL\nInstaller: {installer}\nSHA-256: {digest}", flush=True)


# Deliberately invoke main at module level. This makes the script behave
# identically when launched directly or through runpy and avoids the silent
# no-op seen in the previous package.
main()
