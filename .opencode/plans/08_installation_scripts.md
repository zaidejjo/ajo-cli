# Plan: Cross-Platform Installation Scripts for `ajo` CLI (v2.0)

## 1. Introduction
The goal is to provide a professional, secure, and resilient installation experience for the `ajo` CLI tool across Linux, macOS, and Windows. The scripts will ensure all dependencies are met, verify installation integrity, and provide a fail-safe rollback mechanism.

---

## 2. OS Detection Strategy
The scripts will use a tiered detection approach to identify the environment:

### Unix-like (`install.sh`)
- **Linux/macOS**: Use `uname` to distinguish between `Linux` and `Darwin`.
- **Windows (Git Bash/MSYS2)**: Detect `MSYS` or `MINGW` via `uname` and environment variables like `$OSTYPE`.

### Windows (`install.ps1`)
- **PowerShell**: Native execution on Windows. Use `[System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform` or `$PSVersionTable` to confirm environment.

---

## 3. Dependency Management
The scripts will audit the system for required tools with support for air-gapped environments.

### Requirements
- **Python**: $\ge 3.8$ (checked via `python3 --version` or `python --version`)
- **pip**: Latest version recommended (checked via `pip --version`)
- **git**: Required for cloning/updating (checked via `git --version`)

### Audit Flow
1. **Offline Check**: If `--offline` flag is passed, skip GitHub update checks and attempt installation from local files only.
2. **Check**: Run version checks for each dependency.
3. **Broken Pip Check**: Run `pip --version`; if it fails or returns an error, attempt to repair using `python -m ensurepip`.
4. **Interactive Prompt**: If a dependency is missing, prompt the user: `"Dependency X is missing. Would you like to install it? [y/N]"`.
5. **Non-Interactive Mode**: If `--yes` flag is passed, automatically attempt to install missing dependencies using the system package manager (e.g., `apt`, `brew`, `choco`).
6. **Failure**: If a dependency cannot be installed or network is unreachable (and not in `--offline` mode), provide a specific troubleshooting tip and exit.

---

## 4. Security & Integrity
To ensure a secure installation, the following checks are implemented:

- **Root User Warning**: If the script is run as root/Administrator without the `--force` flag, issue a warning: `"Warning: Running installation as root is not recommended. Please use User mode for a safer install."`
- **Script Integrity**: Check that the script is being executed from the official repository context (verify `.git` folder exists) to prevent execution of modified scripts in untrusted directories.
- **Permission Audit**: Verify write permissions for the chosen installation target before attempting to write files.

---

## 5. Installation Lifecycle

### Update Check (Online Mode)
Before installation, the script will check the GitHub API for the latest release tag. If the local version is outdated, prompt the user: `"A newer version of ajo (vX.Y.Z) is available. Update before installing? [y/N]"`.

### Backup & Rollback
- **Pre-Install Snapshot**: Create a backup of existing `ajo` binaries, config files (`~/.config/ajo`), and shell completion entries.
- **Failure Recovery**: If any step of the installation fails (pip error, disk full, network timeout), the script will:
  1. Trigger the rollback procedure.
  2. Restore the backup.
  3. Clean up partially installed files.
  4. Log the error to `install.log`.

### Logging
All output (stdout and stderr) will be mirrored to a detailed log file at `~/.ajo/install.log` for debugging purposes.

---

## 6. Installation Modes
The user will be prompted to select one of three installation scopes:

| Mode | Target Path | Permissions | Use Case |
|------|-------------|-------------|----------|
| **Global** | `/usr/local/bin` | `sudo` required | System-wide access for all users |
| **User** | `~/.local/bin` | User permissions | Single-user installation (Recommended) |
| **Local** | `./bin` (Project root) | User permissions | Testing or isolated usage |

---

## 7. Core Installation Features

### Installation Mechanism
- **Preferred Method**: Use `pip install .` (or `pip install -e .` for developers).
- **Virtual Environment Option**: Prompt for an isolated venv. If selected, install `ajo` there and create a shim binary in the target bin directory.

### Shell Completions
- Detect active shell (`bash`, `zsh`, `fish`, `tcsh`).
- Run `ajo completion <shell>` and append to shell config.

### Verification
- Run `ajo --version` to verify `PATH` and executable status.

---

## 8. User Experience (UX)

### Visuals
- **Colored Output**: Green (success), Red (error), Yellow (warning).
- **Progress Indicators**: Use `[✓]`, `[!]`, `...` and detailed progress bars for `pip install` (using `--progress-bar` where available).

### Feedback Loop
- **Clear Errors**:- Python not in PATH: `"Python was not found in your PATH. Tip: Add Python to your environment variables."`
- Disk Space: Check for $\ge 100\text{MB}$ free space before installing.
- Network: Handle `ConnectionError` with a tip to check VPN/Proxy settings.

---

## 9. Uninstall Support
The script will include an `--uninstall` flag:
- **Logic**: Identify installation mode.
- **Action**: Run `pip uninstall ajo-cli -y` and remove shims.
- **Clean up**: Offer to remove shell completion entries.

---

## 10. Files to be Created

### 1. `install.sh` (Unix)
- Main entry point for Linux/macOS/Git Bash.
- Implements the full lifecycle: Detection $\rightarrow$ Audit $\rightarrow$ Backup $\rightarrow$ Install $\rightarrow$ Verify.

### 2. `install.ps1` (Windows)
- Main entry point for PowerShell.
- Implements mirrored logic using PowerShell cmdlets and Windows Registry for `PATH` updates.

### 3. `scripts/setup_env.sh` (Helper)
- Internal helper for environment validation used by `install.sh`.

---

## 11. Verification & Testing
- **Test Matrix**: Linux, macOS, Windows (PS/Git Bash) across all 3 modes.
- **Stress Testing**: Simulate network failure, disk full, and missing Python.
- **Rollback Testing**: Force a failure mid-install and verify system is restored to original state.
