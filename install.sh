#!/usr/bin/env bash
set -euo pipefail

REPO_SLUG="${CODEX_WORKFLOWS_REPO:-Monolith-INC/codex-workflows-plugin}"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

usage() {
  cat <<'EOF'
Install codex-workflows-plugin into the application repo you want to govern (not this plugin clone).

Interactive (recommended) — run from your app repo, or confirm the path in the wizard:
  bash <(curl -fsSL https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest/download/install.sh)

Non-interactive / CI:
  curl -fsSL https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest/download/install.sh \
    | bash -s -- --dest /absolute/path/to/your-app
  curl -fsSL https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest/download/install.sh \
    | bash -s -- --dest /absolute/path/to/your-app --target claude
  curl -fsSL https://github.com/Monolith-INC/codex-workflows-plugin/releases/latest/download/install.sh \
    | bash -s -- --dest /absolute/path/to/your-app --uninstall

Environment:
  CODEX_WORKFLOWS_VERSION      Release tag to install, for example v0.5.23. Defaults to latest.
  CODEX_WORKFLOWS_RELEASE_ZIP  Local release zip path, used by tests or offline installs.
  CODEX_WORKFLOWS_REPO         GitHub repo slug. Defaults to Monolith-INC/codex-workflows-plugin.
EOF
}

has_arg() {
  local expected="$1"
  shift
  for arg in "$@"; do
    if [[ "$arg" == "$expected" ]]; then
      return 0
    fi
  done
  return 1
}

download_release_zip() {
  local output="$1"
  if [[ -n "${CODEX_WORKFLOWS_RELEASE_ZIP:-}" ]]; then
    cp "$CODEX_WORKFLOWS_RELEASE_ZIP" "$output"
    return
  fi

  if command -v gh >/dev/null 2>&1; then
    local gh_args=(release download -R "$REPO_SLUG" -p "codex-workflows-plugin-*.zip" -D "$TMP_DIR")
    if [[ -n "${CODEX_WORKFLOWS_VERSION:-}" ]]; then
      gh_args+=("${CODEX_WORKFLOWS_VERSION}")
    fi
    if gh "${gh_args[@]}"; then
      local downloaded
      downloaded="$(find "$TMP_DIR" -maxdepth 1 -type f -name 'codex-workflows-plugin-*.zip' | sort | tail -n 1)"
      if [[ -n "$downloaded" ]]; then
        mv "$downloaded" "$output"
        return
      fi
    fi
  fi

  python3 - "$REPO_SLUG" "${CODEX_WORKFLOWS_VERSION:-}" "$output" <<'PY'
from __future__ import annotations

import json
import sys
import urllib.request

repo, version, output = sys.argv[1:4]
api_url = f"https://api.github.com/repos/{repo}/releases/latest"
if version:
    api_url = f"https://api.github.com/repos/{repo}/releases/tags/{version}"

with urllib.request.urlopen(api_url) as response:
    release = json.load(response)

assets = release.get("assets", [])
zip_assets = [
    asset for asset in assets
    if asset.get("name", "").startswith("codex-workflows-plugin-")
    and asset.get("name", "").endswith(".zip")
]
if not zip_assets:
    raise SystemExit(f"No codex-workflows-plugin release zip found in {release.get('html_url', api_url)}")

download_url = zip_assets[0]["browser_download_url"]
urllib.request.urlretrieve(download_url, output)
PY
}

extract_plugin_tree() {
  local zip_path="$1"
  local output_dir="$2"
  python3 - "$zip_path" "$output_dir" <<'PY'
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

zip_path, output_dir = sys.argv[1:3]
destination = Path(output_dir)
destination.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path) as archive:
    archive.extractall(destination)
required = destination / "scripts" / "installer" / "bootstrap.py"
if not required.is_file():
    raise SystemExit("Release zip does not contain scripts/installer/bootstrap.py")
PY
}

if has_arg "--help" "$@" || has_arg "-h" "$@"; then
  usage
  exit 0
fi

ZIP_PATH="$TMP_DIR/codex-workflows-plugin.zip"
PLUGIN_ROOT="$TMP_DIR/plugin"
CALLER_CWD="$(pwd)"

download_release_zip "$ZIP_PATH"
extract_plugin_tree "$ZIP_PATH" "$PLUGIN_ROOT"

# Run from the extracted tree so -m scripts... resolves package modules from the
# release (not whatever happens to be in the caller's cwd).
cd "$PLUGIN_ROOT"

# No --dest → interactive wizard (prefer: bash <(curl ...); keeps a TTY for prompts).
# Pass the caller's cwd so project detection is not the temp extract tree.
if ! has_arg "--dest" "$@"; then
  if has_arg "--uninstall" "$@"; then
    usage
    echo "error: --uninstall requires --dest, or run with no args for the interactive wizard." >&2
    exit 1
  fi
  exec python3 -m scripts.installer.interactive --zip "$ZIP_PATH" --cwd "$CALLER_CWD"
fi

BOOTSTRAP_ARGS=("$ZIP_PATH")
if ! has_arg "--target" "$@" && ! has_arg "--uninstall" "$@"; then
  BOOTSTRAP_ARGS+=("--target" "all-agents")
fi
BOOTSTRAP_ARGS+=("$@")

exec python3 -m scripts.installer.bootstrap "${BOOTSTRAP_ARGS[@]}"
