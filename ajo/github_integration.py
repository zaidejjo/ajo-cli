"""GitHub integration using gh CLI."""

import subprocess
from pathlib import Path
from rich.console import Console

console = Console()


class GitHubManager:
    """Manage GitHub repository creation and deployment."""

    @staticmethod
    def check_gh_installed() -> bool:
        """Check if GitHub CLI is installed."""
        result = subprocess.run(["gh", "--version"], capture_output=True, text=True)
        return result.returncode == 0

    @staticmethod
    def check_auth() -> bool:
        """Check if user is logged into GitHub."""
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        return result.returncode == 0

    @staticmethod
    def create_repository(project_path: Path, name: str, visibility: str = "public") -> bool:
        """Create GitHub repository and push code."""
        try:
            # Initialize git
            subprocess.run(["git", "init"], cwd=project_path, capture_output=True)
            subprocess.run(["git", "add", "."], cwd=project_path, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "Initial commit from AJO CLI"],
                cwd=project_path,
                capture_output=True,
            )

            # Create and push
            result = subprocess.run(
                [
                    "gh",
                    "repo",
                    "create",
                    name,
                    "--source=.",
                    "--remote=origin",
                    f"--{visibility}",
                    "--push",
                ],
                cwd=project_path,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception as e:
            console.print(f"[red]GitHub error: {e}[/red]")
            return False
