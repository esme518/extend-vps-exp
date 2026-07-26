#!/usr/bin/env bash
set -Eeuo pipefail

export DEBIAN_FRONTEND=noninteractive
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-${SCRIPT_DIR}/.venv}"
USE_VENV="${USE_VENV:-1}"

log() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"
}

die() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

if ! command -v apt-get >/dev/null 2>&1; then
  die "This script only supports Debian/Ubuntu systems with apt-get."
fi

if [ "$(id -u)" -eq 0 ]; then
  SUDO=()
else
  command -v sudo >/dev/null 2>&1 || die "sudo is required when not running as root."
  SUDO=(sudo)
fi

apt_update() {
  log "Updating apt package index..."
  "${SUDO[@]}" apt-get update
}

apt_install() {
  log "Installing: $*"
  "${SUDO[@]}" apt-get install -y --no-install-recommends "$@"
}

apt_install_first_available() {
  local installed=0
  local pkg

  for pkg in "$@"; do
    if apt-cache show "$pkg" >/dev/null 2>&1; then
      apt_install "$pkg"
      installed=1
      break
    fi
  done

  if [ "$installed" -eq 0 ]; then
    die "None of these packages are available: $*"
  fi
}

ensure_base_tools() {
  apt_install \
    ca-certificates \
    curl \
    wget \
    xz-utils \
    bzip2 \
    unzip \
    python3 \
    python3-pip \
    python3-venv

  if ! command -v python >/dev/null 2>&1; then
    apt_install_first_available python-is-python3
  fi
}

ensure_browser_libs() {
  apt_install_first_available libgtk-3-0t64 libgtk-3-0
  apt_install_first_available libasound2t64 libasound2
  apt_install_first_available libatk-bridge2.0-0t64 libatk-bridge2.0-0
  apt_install_first_available libatk1.0-0t64 libatk1.0-0
  apt_install_first_available libcups2t64 libcups2
  apt_install_first_available libatspi2.0-0t64 libatspi2.0-0

  apt_install \
    dbus \
    xvfb \
    ffmpeg \
    fonts-liberation \
    fonts-noto-cjk \
    libdbus-glib-1-2 \
    libxt6 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libcairo2 \
    libdrm2 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libnss3 \
    libnspr4 \
    libxss1 \
    libxshmfence1
}

resolve_python() {
  if [ "$USE_VENV" = "1" ]; then
    log "Creating/updating Python virtualenv: ${VENV_DIR}"
    python3 -m venv "$VENV_DIR"
    PYTHON_BIN="${VENV_DIR}/bin/python"
  else
    PYTHON_BIN="${PYTHON_BIN:-python3}"
  fi

  "$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
}

install_python_deps() {
  if [ -f "${SCRIPT_DIR}/requirements.txt" ]; then
    log "Installing Python dependencies from requirements.txt..."
    "$PYTHON_BIN" -m pip install -r "${SCRIPT_DIR}/requirements.txt"
  else
    log "requirements.txt not found; installing core packages only..."
    "$PYTHON_BIN" -m pip install 'camoufox[geoip]' aiohttp playwright-captcha
  fi

  "$PYTHON_BIN" -m pip install --upgrade camoufox browserforge
}

install_playwright_deps() {
  log "Installing Playwright Firefox OS dependencies..."
  "$PYTHON_BIN" -m playwright install-deps firefox
}

fetch_camoufox() {
  log "Fetching Camoufox browser binary..."
  "$PYTHON_BIN" -m camoufox fetch
}

verify_installation() {
  log "Verifying Camoufox installation..."
  "$PYTHON_BIN" - <<'PY'
import asyncio
from camoufox.async_api import AsyncCamoufox

async def main():
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=60000)
        print(await page.title())

asyncio.run(main())
PY
}

apt_update
ensure_base_tools
ensure_browser_libs
resolve_python
install_python_deps
install_playwright_deps
fetch_camoufox
verify_installation

log "Done. Use this Python for the bot: ${PYTHON_BIN}"
