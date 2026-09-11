# PyInstaller spec for Fiducia Facture (Windows 64-bit).
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

project = Path(SPECPATH).parent
app_dir = project / "app"

# Keep application assets inside the frozen application bundle.
# app/assets  → app/assets  (logo.jpeg used by pdf_export)
# assets/     → assets/     (icons: select-mode-off.png, select-mode-on.png, .ico)
datas = [(str(app_dir / "assets"), "app/assets")]
datas += [(str(project / "assets"), "assets")]
datas += collect_data_files("customtkinter")

hiddenimports = [
    "customtkinter",
]

a = Analysis(
    [str(project / "main.py")],
    pathex=[str(project)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "app.telegram_backup",
        "certifi",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Fiducia Facture",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(project / "assets" / "FiduciaFacture.ico"),
)

# onedir is intentional: Inno Setup installs this complete application folder
# under Program Files and can replace it safely during upgrades.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Fiducia Facture",
)
