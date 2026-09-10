"""Single source of truth for the application version and update channel."""

APP_NAME = "Fiducia Facture"
APP_VERSION = "1.0.2"
UPDATE_CHANNEL = "stable"

# Fill these in before publishing the first release. Releases should contain
# the installer and its .sha256 sidecar file.
GITHUB_OWNER = "yt-dev-sys"
GITHUB_REPOSITORY = "fiducia-facture"


def github_releases_url() -> str:
    return f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases/latest"
