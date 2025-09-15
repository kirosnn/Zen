import importlib
import subprocess
import sys
from typing import Iterator, Tuple, Optional, List

try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata

from loader import SingleBrailleLoader

try:
    from packaging.requirements import Requirement
    PACKAGING_AVAILABLE = True
except Exception:
    PACKAGING_AVAILABLE = False


def iter_requirements(filename: str) -> Iterator[str]:
    with open(filename, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "#" in line and not line.lstrip().startswith(("http://", "https://")):
                line = line.split("#", 1)[0].strip()
            if line:
                yield line


def requirement_status(spec: str) -> Tuple[str, str, Optional[str]]:
    if PACKAGING_AVAILABLE:
        try:
            req = Requirement(spec)
        except Exception:
            return "install", spec, None

        try:
            installed_version = metadata.version(req.name)
        except metadata.PackageNotFoundError:
            return "install", spec, None

        if req.specifier and not req.specifier.contains(installed_version, prereleases=True):
            return "upgrade", spec, installed_version

        return "skip", spec, installed_version

    if spec.isidentifier():
        try:
            importlib.import_module(spec)
            return "skip", spec, None
        except ModuleNotFoundError:
            return "install", spec, None

    return "install", spec, None


def pip_install(spec: str) -> Tuple[int, str]:
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check",
        "-q",
        spec,
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    return result.returncode, result.stdout


def install_packages_from_file(filename: str = "utils/requirements.txt", retry_failed: bool = True, max_retries: int = 3) -> None:
    specs = list(iter_requirements(filename))
    if not specs:
        print(f"No requirements found in {filename}.")
        return

    print(f"Processing {len(specs)} requirement(s) from {filename}...")
    
    loader = SingleBrailleLoader(total=len(specs))
    loader.update_every = 0.1
    
    loader.start()
    
    try:
        failed_specs: List[str] = []
        installed_count = 0
        upgraded_count = 0
        skipped_count = 0

        for i, spec in enumerate(specs, 1):
            display_spec = spec if len(spec) <= 30 else spec[:27] + "..."
            
            action, _, installed_version = requirement_status(spec)

            if action == "skip":
                loader.set_status(f"✓ {display_spec} (already installed)")
                skipped_count += 1
                loader.update()
                continue

            verb = "Installing" if action == "install" else "Upgrading"
            success = False
            
            for attempt in range(max_retries if retry_failed else 1):
                loader.set_status(f"{verb} {display_spec}...")
                
                code, output = pip_install(spec)
                
                if code == 0:
                    if action == "install":
                        installed_count += 1
                        loader.set_status(f"✓ {display_spec} installed")
                    else:
                        upgraded_count += 1
                        loader.set_status(f"✓ {display_spec} upgraded")
                    success = True
                    break
                elif attempt < max_retries - 1 and retry_failed:
                    loader.set_status(f"⟳ Retrying {display_spec} ({attempt + 2}/{max_retries})...")
                else:
                    loader.set_status(f"✗ Failed: {display_spec}")
                    failed_specs.append(spec)

            if not success and spec not in failed_specs:
                failed_specs.append(spec)

            loader.update()
    
    finally:
        loader.finish()

    if failed_specs:
        print("\nFailed packages:")
        for spec in failed_specs:
            print(f"  ✗ {spec}")
        print("\nYou may want to install these manually.")
    else:
        print("\n✓ All packages processed successfully!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Install Python packages from requirements file.")
    parser.add_argument("--file", "-f", default="utils/requirements.txt", help="Path to requirements file")
    parser.add_argument("--no-retry", action="store_true", help="Disable retry on failed installations")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum number of retries (default: 3)")

    args = parser.parse_args()
    install_packages_from_file(
        filename=args.file,
        retry_failed=not args.no_retry,
        max_retries=args.max_retries
    )