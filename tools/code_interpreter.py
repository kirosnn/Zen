import os
import sys
import subprocess
import tempfile
import shutil
import uuid
import time
from datetime import datetime, timezone
from utils.sandbox_security import validate_code_ast, CodeSafetyError

DEFAULT_DOCKER_IMAGE = os.getenv("SANDBOX_DOCKER_IMAGE", "python:3.11-slim")
SANDBOX_BASE_DIR = os.getenv("SANDBOX_BASE_DIR", os.path.abspath("./sandbox_runs"))
SANDBOX_OUTPUT_DIR = os.getenv("SANDBOX_OUTPUT_DIR", os.path.abspath("./output"))
SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "30"))
SANDBOX_MEMORY = os.getenv("SANDBOX_MEMORY", "512m")
SANDBOX_CPUS = os.getenv("SANDBOX_CPUS", "1.0")
MAX_STDOUT_CHARS = int(os.getenv("SANDBOX_MAX_STDOUT", "10000"))

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def make_run_workspace():
    ensure_dir(SANDBOX_BASE_DIR)
    uid = uuid.uuid4().hex[:8]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    workspace = os.path.join(SANDBOX_BASE_DIR, f"run_{stamp}_{uid}")
    ensure_dir(workspace)
    return os.path.abspath(workspace)

def write_script(workspace, code, filename="script.py"):
    script_path = os.path.join(workspace, filename)
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(code)
    os.chmod(script_path, 0o600)
    return script_path

def copy_artifacts_to_output(workspace):
    ensure_dir(SANDBOX_OUTPUT_DIR)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_subdir = os.path.join(SANDBOX_OUTPUT_DIR, f"run_{timestamp}")
    ensure_dir(output_subdir)
    
    copied_files = []
    for root, _, filenames in os.walk(workspace):
        for fn in filenames:
            if fn == "script.py":
                continue
                
            src_path = os.path.join(root, fn)
            rel_path = os.path.relpath(src_path, workspace)
            dst_path = os.path.join(output_subdir, rel_path)
            
            dst_dir = os.path.dirname(dst_path)
            if dst_dir:
                ensure_dir(dst_dir)
            
            shutil.copy2(src_path, dst_path)
            copied_files.append(dst_path)
    
    return copied_files

def collect_artifacts(workspace, keep_script=True):
    files = []
    for root, _, filenames in os.walk(workspace):
        for fn in filenames:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, workspace)
            files.append(rel)
    
    copied_files = copy_artifacts_to_output(workspace)
    
    zip_path = None
    if files:
        zip_name = f"artifacts_{os.path.basename(workspace)}.zip"
        zip_path = os.path.join(SANDBOX_BASE_DIR, zip_name)
        shutil.make_archive(zip_path.replace(".zip", ""), "zip", workspace)
    
    return files, zip_path, copied_files

def check_docker_available():
    if not shutil.which("docker"):
        return False
    
    try:
        result = subprocess.run(
            ["docker", "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False

def pull_docker_image(image):
    try:
        result = subprocess.run(
            ["docker", "images", "-q", image],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if not result.stdout.strip():
            print(f"[SECURE-RUN] Pulling Docker image {image}...")
            pull_result = subprocess.run(
                ["docker", "pull", image],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300
            )
            return pull_result.returncode == 0
        return True
    except Exception as e:
        print(f"[SECURE-RUN] Error pulling image: {e}")
        return False

class LocalCodeInterpreterTool:
    name = "Local Code Interpreter (Sandboxed Docker)"
    description = "Execute Python snippets inside a restricted Docker container with AST checks and artifact collection."

    def __init__(self, docker_image=DEFAULT_DOCKER_IMAGE, timeout=SANDBOX_TIMEOUT, memory=SANDBOX_MEMORY, cpus=SANDBOX_CPUS, use_custom_image=False):
        self.docker_image = docker_image
        self.timeout = timeout
        self.memory = memory
        self.cpus = cpus
        self.use_custom_image = use_custom_image
        if use_custom_image:
            self._build_custom_image()

    def _build_custom_image(self):
        dockerfile_content = """
FROM python:3.11-slim

RUN pip install --no-cache-dir \
    numpy \
    pandas \
    matplotlib \
    pillow \
    requests \
    beautifulsoup4

WORKDIR /workspace
"""
        temp_dir = tempfile.mkdtemp()
        dockerfile_path = os.path.join(temp_dir, "Dockerfile")
        
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content)
        
        try:
            print("[SECURE-RUN] Building custom Docker image with pre-installed packages...")
            subprocess.run(
                ["docker", "build", "-t", "python-sandbox:custom", temp_dir],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.docker_image = "python-sandbox:custom"
            print("[SECURE-RUN] Custom image built successfully!")
        except subprocess.CalledProcessError:
            print("[SECURE-RUN] Failed to build custom image, using default.")
        finally:
            shutil.rmtree(temp_dir)

    def _run(self, code, extra_files=None):
        try:
            validate_code_ast(code)
        except CodeSafetyError as e:
            return f"[SECURE-RUN] Code rejected by security validation: {e}"

        if not check_docker_available():
            return (
                "[SECURE-RUN] Docker is not available or not running.\n"
                "Please ensure Docker Desktop is installed and running.\n"
                "On Windows: Start Docker Desktop from the Start Menu.\n"
                "On Linux/Mac: Ensure Docker daemon is running (sudo systemctl start docker)."
            )

        if not pull_docker_image(self.docker_image):
            return f"[SECURE-RUN] Failed to pull Docker image: {self.docker_image}"

        workspace = make_run_workspace()
        script_path = write_script(workspace, code, filename="script.py")

        if extra_files:
            for fname, data in extra_files:
                safe_fname = os.path.join(workspace, os.path.basename(fname))
                with open(safe_fname, "wb") as f:
                    f.write(data)
                os.chmod(safe_fname, 0o600)

        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", str(self.memory),
            "--cpus", str(self.cpus),
            "--pids-limit", "128",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "-v", f"{workspace}:/workspace:rw",
            "--workdir", "/workspace",
            self.docker_image,
            "python", "-u", "script.py"
        ]

        start_time = time.time()
        try:
            proc = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=self.timeout
            )
            raw_output = proc.stdout or ""
            execution_time = time.time() - start_time
        except subprocess.TimeoutExpired:
            raw_output = "[SECURE-RUN] Timeout: execution exceeded the limit and was interrupted."
            execution_time = self.timeout
        except FileNotFoundError as e:
            raw_output = f"[SECURE-RUN] Error: docker not found or not accessible: {e}"
            execution_time = time.time() - start_time
        except Exception as e:
            raw_output = f"[SECURE-RUN] Execution error: {e}"
            execution_time = time.time() - start_time

        if len(raw_output) > MAX_STDOUT_CHARS:
            truncated_marker = f"\n...[truncated output, total length {len(raw_output)} chars]..."
            stdout_display = raw_output[:MAX_STDOUT_CHARS] + truncated_marker
        else:
            stdout_display = raw_output

        artifact_list, zip_path, copied_files = collect_artifacts(workspace)

        res_lines = [
            "[SECURE-RUN] Execution summary:",
            "",
            f"Docker image: {self.docker_image}",
            f"Timeout (s): {self.timeout}",
            f"Memory: {self.memory}, CPUs: {self.cpus}",
            f"Execution time: {execution_time:.2f}s",
        ]
        
        if stdout_display:
            res_lines.extend([
                "",
                "[SECURE-RUN] STDOUT / STDERR (limited):",
                stdout_display,
            ])
        
        res_lines.extend([
            "",
            "[SECURE-RUN] Artifacts saved in workspace:",
            "",
            f"workspace dir: {workspace}"
        ])
        
        if artifact_list:
            res_lines.append(f"files: {', '.join(artifact_list)}")
            if zip_path:
                res_lines.append(f"zip: {zip_path}")
            if copied_files:
                res_lines.extend([
                    "",
                    "[SECURE-RUN] Files copied to output directory:",
                    f"output dir: {SANDBOX_OUTPUT_DIR}"
                ])
                for file in copied_files:
                    res_lines.append(f"  - {file}")
        else:
            res_lines.append("(no files generated in workspace)")

        return "\n".join(res_lines)


def main():
    running_in_tests = bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("CI", "").lower() in {"1", "true", "yes"}
    docker_available = check_docker_available()
    force_demo = os.getenv("RUN_INTERPRETER_DEMO", "").lower() in {"1", "true", "yes"}

    if (running_in_tests or not docker_available) and not force_demo:
        reason = []
        if running_in_tests:
            reason.append("test/CI environment detected")
        if not docker_available:
            reason.append("Docker not available or not running")
            print(f"[SECURE-RUN] Skipping demo execution ({'; '.join(reason)}).")
            print("\nTo use this tool, please ensure Docker Desktop is running:")
            print("- Windows: Start Docker Desktop from the Start Menu")
            print("- Linux/Mac: Ensure Docker daemon is running (sudo systemctl start docker)")
            return 0
        print(f"[SECURE-RUN] Skipping demo execution ({'; '.join(reason)}).")
        return 0

    tool = LocalCodeInterpreterTool(use_custom_image=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())