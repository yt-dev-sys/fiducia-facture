"""Write the release tag (e.g. v2.0.3) into app/version.py so the installer and the
running app always report the same version as the GitHub release."""
import re
import sys
from pathlib import Path

tag = sys.argv[1].strip()
version = tag.lstrip("vV")
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    raise SystemExit(f"Tag '{tag}' is not of the form vX.Y.Z")

path = Path(__file__).resolve().parent.parent / "app" / "version.py"
text = path.read_text(encoding="utf-8-sig")
new, count = re.subn(r'APP_VERSION\s*=\s*"[^"]*"', f'APP_VERSION = "{version}"', text, count=1)
if count != 1:
    raise SystemExit("APP_VERSION not found in app/version.py")
path.write_text(new, encoding="utf-8")
print(f"APP_VERSION set to {version}")
