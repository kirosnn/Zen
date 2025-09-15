import subprocess
import sys
import time
import requests
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class OllamaInstaller:
    """Utility class for installing and managing Ollama on Windows."""

    def __init__(self, model: str = "mistral:7b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def is_ollama_installed(self) -> bool:
        """Check if Ollama is installed on the system."""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def install_ollama(self) -> Tuple[bool, str]:
        """Install Ollama using winget or provide manual instructions."""
        try:
            # Try to install using winget
            print("Installing Ollama using winget...")
            result = subprocess.run(
                ["winget", "install", "--id", "Ollama.Ollama", "--accept-source-agreements", "--accept-package-agreements"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300  # 5 minutes timeout
            )

            if result.returncode == 0:
                print("✓ Ollama installed successfully!")
                return True, "Installed via winget"
            else:
                return False, f"Winget installation failed: {result.stderr}"

        except (subprocess.TimeoutExpired, FileNotFoundError):
            # Winget not available or failed
            manual_instructions = """
Ollama is not installed. Please install it manually:

1. Download Ollama from: https://ollama.ai/download/OllamaSetup.exe
2. Run the installer
3. Restart this application

Alternatively, if winget is available, run:
winget install --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
"""
            return False, manual_instructions

    def is_ollama_running(self) -> bool:
        """Check if Ollama service is running."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def start_ollama(self) -> Tuple[bool, str]:
        """Start the Ollama service."""
        try:
            print("Starting Ollama service...")
            # Start ollama serve in background
            process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            # Wait a bit for service to start
            time.sleep(3)

            if self.is_ollama_running():
                print("✓ Ollama service started successfully!")
                return True, "Service started"
            else:
                return False, "Service failed to start"

        except (subprocess.SubprocessError, FileNotFoundError) as e:
            return False, f"Failed to start Ollama: {str(e)}"

    def is_model_available(self, model: Optional[str] = None) -> bool:
        """Check if a specific model is available."""
        model = model or self.model
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return any(m.get("name") == model for m in models)
            return False
        except requests.RequestException:
            return False

    def pull_model(self, model: Optional[str] = None) -> Tuple[bool, str]:
        """Pull a model from Ollama registry."""
        model = model or self.model
        try:
            print(f"Pulling model {model}...")
            result = subprocess.run(
                ["ollama", "pull", model],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=600  # 10 minutes timeout for model download
            )

            if result.returncode == 0:
                print(f"✓ Model {model} pulled successfully!")
                return True, "Model pulled"
            else:
                return False, f"Failed to pull model: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, f"Timeout pulling model {model}"
        except FileNotFoundError:
            return False, "Ollama command not found"

    def ensure_ollama_ready(self) -> Tuple[bool, str]:
        """Ensure Ollama is installed, running, and has the required model."""
        messages = []

        # Check if installed
        if not self.is_ollama_installed():
            success, msg = self.install_ollama()
            messages.append(msg)
            if not success:
                return False, "\n".join(messages)

        # Check if running
        if not self.is_ollama_running():
            success, msg = self.start_ollama()
            messages.append(msg)
            if not success:
                return False, "\n".join(messages)

            # Give it a moment after starting
            time.sleep(2)

        # Check if model is available
        if not self.is_model_available():
            success, msg = self.pull_model()
            messages.append(msg)
            if not success:
                return False, "\n".join(messages)

        return True, "✓ Ollama is ready!"

def setup_ollama(model: str = "mistral:7b", base_url: str = "http://localhost:11434") -> bool:
    """Convenience function to set up Ollama completely."""
    installer = OllamaInstaller(model, base_url)
    success, message = installer.ensure_ollama_ready()

    if success:
        print(message)
    else:
        print("Failed to set up Ollama:")
        print(message)

    return success

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Install and set up Ollama for Zen.")
    parser.add_argument("--model", default="mistral:7b", help="Model to pull (default: mistral:7b)")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL")

    args = parser.parse_args()
    setup_ollama(args.model, args.base_url)
