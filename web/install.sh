#!/usr/bin/env bash

# ajo-cli installation script
# Optimized for speed, reliability, and security.

set -euo pipefail

# Exit codes
EXIT_SUCCESS=0
EXIT_GENERAL=1
EXIT_DEPENDENCY_MISSING=2
EXIT_PERMISSION_DENIED=3
EXIT_NETWORK_ERROR=4

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Flags
DRY_RUN=false
TEST_MODE=false
USER_INSTALL=true

# Function to print messages
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Function to handle cleanup on exit
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ] && [ $exit_code -ne $EXIT_SUCCESS ]; then
        log_error "Installation failed with exit code $exit_code."
    fi
    exit $exit_code
}
trap cleanup EXIT

# Function to handle Ctrl+C
trap 'log_error "\nInstallation interrupted by user."; exit 1' INT TERM

# Function to show help
show_help() {
    echo "Usage: install.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --user          Install for the current user (default)"
    echo "  --global        Install globally (requires sudo/root)"
    echo "  --test          Run in test mode (simulation)"
    echo "  --dry-run       Preview actions without making changes"
    echo "  --help          Show this help message"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --user) USER_INSTALL=true; shift ;;
        --global) USER_INSTALL=false; shift ;;
        --test) TEST_MODE=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help) show_help; exit 0 ;;
        *) log_error "Unknown option: $1"; show_help; exit $EXIT_GENERAL ;;
    esac
done

# Check if running via pipe
if [[ ! -t 0 ]]; then
    log_info "Running in pipe mode (curl | sh)..."
fi

# Check for dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not found. Please install Python 3.8+."
        exit $EXIT_DEPENDENCY_MISSING
    fi
    if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
        log_error "pip is required but not found. Please install pip."
        exit $EXIT_DEPENDENCY_MISSING
    fi
    if ! command -v git &> /dev/null; then
        log_warn "git is not installed. Some features might not work."
    fi
}

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)     OS="Linux";;
        Darwin*)    OS="macOS";;
        CYGNW*)     OS="Windows";;
        *)          OS="Unknown";;
    esac
    log_info "Detected OS: $OS"
    if [ "$OS" = "Unknown" ]; then
        log_error "Unsupported operating system."
        exit $EXIT_GENERAL
    fi
}

# Perform installation
install_ajo() {
    log_info "Starting installation of ajo-cli..."
    
    # In a real scenario, we would download the package from PyPI or a URL.
    # For this task, we'll assume we are installing from a URL or a local file if we were in a real environment.
    # Since this is a script that will be served, it should probably use pip install ajo-cli.
    
    local install_cmd=""
    if [ "$USER_INSTALL" = true ]; then
        install_cmd="pip3 install --user ajo-cli"
    else
        install_cmd="sudo pip3 install ajo-cli"
    fi

    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY-RUN] Would execute: $install_cmd"
        return 0
    fi

    if [ "$TEST_MODE" = true ]; then
        log_info "[TEST-MODE] Simulating installation..."
        sleep 1
        log_success "Simulated installation complete."
        return 0
    fi

    log_info "Executing: $install_cmd"
    if ! eval "$install_cmd"; then
        log_error "Failed to install ajo-cli."
        exit $EXIT_GENERAL
    fi
}

# Main execution
main() {
    check_dependencies
    detect_os
    install_ajo
    
    log_success "ajo-cli installed successfully!"
    log_info "Verify installation by running: ajo --version"
}

main
