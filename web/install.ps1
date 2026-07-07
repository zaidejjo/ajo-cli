# ajo-cli installation script for Windows PowerShell
# Optimized for speed, reliability, and security.

$ErrorActionPreference = "Stop"

# Exit codes
$EXIT_SUCCESS = 0
$EXIT_GENERAL = 1
$EXIT_DEPENDENCY_MISSING = 2
$EXIT_PERMISSION_DENIED = 3
$EXIT_NETWORK_ERROR = 4

# Colors for output
function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[SUCCESS] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-ErrorMsg($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# Flags
$DryRun = $false
$TestMode = $false
$UserInstall = $true

function Show-Help {
    Write-Host "Usage: install.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  --user          Install for the current user (default)"
    Write-Host "  --global        Install globally"
    Write-Host "  --test          Run in test mode (simulation)"
    Write-Host "  --dry-run       Preview actions without making changes"
    Write-Host "  --help          Show this help message"
}

# Parse arguments
foreach ($arg in $args) {
    switch ($arg) {
        "--user" { $UserInstall = $true }
        "--global" { $UserInstall = $false }
        "--test" { $TestMode = $true }
        "--dry-run" { $DryRun = $true }
        "--help" { Show-Help; exit $EXIT_SUCCESS }
        Default { Write-ErrorMsg "Unknown option: $arg"; Show-Help; exit $EXIT_GENERAL }
    }
}

# Check if running via pipe (not easily detectable in PS like in Bash, but we can check if it's interactive)
if (-not [Console]::IsInputRedirected) {
    Write-Info "Running in interactive mode..."
} else {
    Write-Info "Running in pipe mode..."
}

# Check for dependencies
function Check-Dependencies {
    Write-Info "Checking dependencies..."
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-ErrorMsg "Python is required but not found. Please install Python 3.8+."
        exit $EXIT_DEPENDENCY_MISSING
    }
    if (-not (Get-Command pip -ErrorAction SilentlyContinue)) {
        Write-ErrorMsg "pip is required but not found. Please install pip."
        exit $EXIT_DEPENDENCY_MISSING
    }
}

# Detect OS (though this script is specifically for Windows)
function Detect-OS {
    Write-Info "Detected OS: Windows"
}

# Perform installation
function Install-Ajo {
    Write-Info "Starting installation of ajo-cli..."
    
    $installCmd = if ($UserInstall) { "pip install --user ajo-cli" } else { "pip install ajo-cli" }

    if ($DryRun) {
        Write-Info "[DRY-RUN] Would execute: $installCmd"
        return
    }

    if ($TestMode) {
        Write-Info "[TEST-MODE] Simulating installation..."
        Start-Sleep -Seconds 1
        Write-Success "Simulated installation complete."
        return
    }

    Write-Info "Executing: $installCmd"
    try {
        Invoke-Expression $installCmd
        Write-Success "ajo-cli installed successfully!"
        Write-Info "Verify installation by running: ajo --version"
    } catch {
        Write-ErrorMsg "Failed to install ajo-cli: $_"
        exit $EXIT_GENERAL
    }
}

# Main
try {
    Check-Dependencies
    Detect-OS
    Install-Ajo
} catch {
    Write-ErrorMsg "An error occurred: $_"
    exit $EXIT_GENERAL
}
