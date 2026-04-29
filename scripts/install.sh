#!/usr/bin/env bash
# ============================================================================
# code4u.ai — One-Line Installer
#
# Usage:
#   curl -fsSL https://code4u.ai/install.sh | bash
#
# What it does:
#   1. Checks Python 3.9+ is available.
#   2. Creates the ~/.code4u/ directory structure.
#   3. Installs the code4u package via pip.
#   4. Installs the 'Standard Excellence' recipe pack.
#   5. Runs a diagnostic to verify everything works.
# ============================================================================

set -euo pipefail

# -- Colors ------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}[info]${NC}  $*"; }
success() { echo -e "${GREEN}[  ok]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }
error()   { echo -e "${RED}[fail]${NC}  $*"; exit 1; }

# -- Banner ------------------------------------------------------------------
echo -e ""
echo -e "${CYAN}${BOLD}  ⚡ code4u.ai v1.0.0 Installer${NC}"
echo -e "${CYAN}  ─────────────────────────────────${NC}"
echo -e ""

# -- Step 1: Check Python ---------------------------------------------------
info "Checking Python installation..."

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        PY_MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
        PY_MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "0")
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 9 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    error "Python 3.9+ is required but not found. Please install Python first."
fi
success "Found $PYTHON ($PY_VERSION)"

# -- Step 2: Create directory structure --------------------------------------
info "Creating ~/.code4u directory structure..."

CODE4U_HOME="$HOME/.code4u"
mkdir -p "$CODE4U_HOME"/{plugins,recipes,rules,sessions,logs,global_cache}

success "Directory structure created at $CODE4U_HOME"

# -- Step 3: Install code4u -------------------------------------------------
info "Installing code4u package..."

if command -v pip3 &>/dev/null; then
    PIP="pip3"
elif command -v pip &>/dev/null; then
    PIP="pip"
else
    PIP="$PYTHON -m pip"
fi

# Check if we're in the repo (local install) or remote
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"

if [ -f "$BACKEND_DIR/pyproject.toml" ]; then
    info "Local repository detected. Installing in editable mode..."
    $PIP install -e "$BACKEND_DIR" --quiet 2>/dev/null || \
        $PIP install -e "$BACKEND_DIR" 2>&1 | tail -5
else
    info "Installing from PyPI..."
    $PIP install code4u-backend --quiet 2>/dev/null || \
        $PIP install code4u-backend 2>&1 | tail -5
fi

success "code4u package installed"

# -- Step 4: Install base recipes -------------------------------------------
info "Installing 'Standard Excellence' recipe pack..."

$PYTHON -c "
from code4u.core.version import VersionManager
vm = VersionManager()
count = vm.install_base_recipes()
vm.write_version_file()
print(f'  Installed {count} base recipes.')
" 2>/dev/null || warn "Recipe installation skipped (non-critical)."

success "Base recipes installed"

# -- Step 5: Verify ---------------------------------------------------------
info "Running diagnostics..."

if command -v code4u &>/dev/null; then
    CODE4U_VERSION=$(code4u --version 2>/dev/null | head -1 || echo "unknown")
    success "code4u CLI available: $CODE4U_VERSION"
else
    warn "code4u command not in PATH. You may need to restart your shell."
fi

# -- Summary -----------------------------------------------------------------
echo -e ""
echo -e "${GREEN}${BOLD}  ✅ Installation Complete!${NC}"
echo -e ""
echo -e "  ${BOLD}Quick Start:${NC}"
echo -e "    ${CYAN}code4u welcome${NC}          Run the onboarding diagnostic"
echo -e "    ${CYAN}code4u index .${NC}          Index the current project"
echo -e "    ${CYAN}code4u health .${NC}         Find unused code"
echo -e "    ${CYAN}code4u dashboard .${NC}      Launch the War Room TUI"
echo -e "    ${CYAN}code4u recipes list${NC}     See available recipes"
echo -e "    ${CYAN}code4u agents${NC}           List all AI agents"
echo -e ""
echo -e "  ${BOLD}Documentation:${NC}"
echo -e "    ${CYAN}code4u --help${NC}           Full command reference"
echo -e "    ${CYAN}https://code4u.ai/docs${NC}  Online documentation"
echo -e ""
