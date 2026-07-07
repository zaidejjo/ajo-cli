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

# Check if running via pipe
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
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Warn "git is not installed. It will be required if we fallback to source installation."
    }
}

# Detect OS
function Detect-OS {
    Write-Info "Detected OS: Windows"
}

# Function to install uv
function Install-Uv {
    Write-Info "Installing uv..."
    try {
        powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
        
        # Update current session path
        $uvPath = Join-Path $HOME ".cargo\bin"
        if ($env:Path -notlike "*$uvPath*") {
            $env:Path += ";$uvPath"
        }
        
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            Write-Success "uv installed successfully!"
            return $true
        } else {
            Write-ErrorMsg "uv installed but not found in PATH."
            return $false
        }
    } catch {
        Write-ErrorMsg "Failed to install uv: $_"
        return $false
    }
}

# Perform installation
function Install-Ajo {
    Write-Info "Starting installation of ajo-cli..."
    
    if ($DryRun) {
        Write-Info "[DRY-RUN] Would attempt installation via uv (with optional install), then pipx, then source."
        return
    }

    if ($TestMode) {
        Write-Info "[TEST-MODE] Simulating installation..."
        Start-Sleep -Seconds 1
        Write-Success "Simulated installation complete."
        return
    }

    # 1. Try uv
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        # Only prompt if interactive
        if (-not [Console]::IsInputRedirected) {
            $response = Read-Host "uv is not installed. Would you like to install it first? [Y/n]"
            if ([string]::IsNullOrWhiteSpace($response) -or $response -eq 'Y' -or $response -eq 'y') {
                if (-not (Install-Uv)) {
                    Write-Warn "uv installation failed. Moving to next fallback..."
                }
            } else {
                Write-Info "Skipping uv installation."
            }
        } else {
            Write-Info "Non-interactive session. Skipping uv prompt."
        }
    }

    if (Get-Command uv -ErrorAction SilentlyContinue) {
        Write-Info "Using 'uv' to install ajo-cli..."
        try {
            uv tool install ajo-cli
            Write-Success "ajo-cli installed successfully via uv!"
            return
        } catch {
            Write-ErrorMsg "Failed to install via uv: $_"
            exit $EXIT_GENERAL
        }
    }

    # 2. Try pipx
    if (Get-Command pipx -ErrorAction SilentlyContinue) {
        Write-Info "Found 'pipx'. Installing via pipx..."
        try {
            pipx install ajo-cli
            Write-Success "ajo-cli installed successfully via pipx!"
            return
        } catch {
            Write-ErrorMsg "Failed to install via pipx: $_"
            exit $EXIT_GENERAL
        }
    }

    # 3. Fallback to source
    Write-Warn "Neither 'uv' nor 'pipx' found. Falling back to source installation..."
    
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-ErrorMsg "git is required for source installation but not found."
        exit $EXIT_DEPENDENCY_MISSING
    }

    $repoDir = "ajo-cli-temp"
    if (Test-Path $repoDir) { Remove-Item -Recurse -Force $repoDir }

    Write-Info "Cloning repository to $repoDir..."
    try {
        git clone --depth 1 https://github.com/zaidejjo/ajo-cli.git $repoDir
    } catch {
        Write-ErrorMsg "Failed to clone repository: $_"
        exit $EXIT_NETWORK_ERROR
    }

    Set-Location $repoDir
    
    $installCmd = if ($UserInstall) { "pip install ." } else { "pip install ." } # Windows global usually requires admin shell
    
    Write-Info "Installing from source using $installCmd..."
    try {
        Invoke-Expression $installCmd
    } catch {
        Write-ErrorMsg "Failed to install from source: $_"
        Set-Location ..
        Remove-Item -Recurse -Force $repoDir
        exit $EXIT_GENERAL
    }
    Set-Location ..

    Write-Info "Cleaning up source code..."
    Remove-Item -Recurse -Force $repoDir

    Write-Success "ajo-cli installed successfully from source!"
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
