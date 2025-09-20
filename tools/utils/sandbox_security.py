import os
import sys
import ast
import fnmatch

DEFAULT_FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib", "ctypes", "multiprocessing",
    "threading", "selectors", "resource", "psutil"
}
DEFAULT_FORBIDDEN_BUILTINS = {"exec", "eval", "compile", "__import__", "open", "input"}
DEFAULT_FORBIDDEN_ATTRS = {
    "system", "popen", "Popen", "run", "call", "check_call", "check_output",
    "remove", "unlink", "rmdir", "walk", "fork", "spawn", "execv", "execve",
    "kill", "terminate", "connect", "send", "recv"
}

RAW_ALLOWED_IMPORTS = os.getenv("SANDBOX_ALLOWED_IMPORTS", "")
ALLOWED_IMPORT_PATTERNS = [p.strip() for p in RAW_ALLOWED_IMPORTS.split(",") if p.strip()]

FORBIDDEN_MODULES = DEFAULT_FORBIDDEN_MODULES
FORBIDDEN_BUILTINS = DEFAULT_FORBIDDEN_BUILTINS
FORBIDDEN_ATTRS = DEFAULT_FORBIDDEN_ATTRS

class CodeSafetyError(Exception):
    pass

def _is_import_allowed(module_name):
    if not ALLOWED_IMPORT_PATTERNS:
        return True
    root = module_name.split(".")[0] if module_name else ""
    for pat in ALLOWED_IMPORT_PATTERNS:
        if fnmatch.fnmatch(module_name, pat) or fnmatch.fnmatch(root, pat):
            return True
    return False

def validate_code_ast(code):
    try:
        tree = ast.parse(code)
    except Exception as e:
        raise CodeSafetyError(f"AST parsing error: {e}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in FORBIDDEN_MODULES:
                    raise CodeSafetyError(f"Forbidden import detected: {alias.name}")
                if not _is_import_allowed(alias.name):
                    raise CodeSafetyError(f"Import not allowed by policy: {alias.name}")

        if isinstance(node, ast.ImportFrom):
            mod = (node.module or "")
            root = mod.split(".")[0] if mod else ""
            if root in FORBIDDEN_MODULES:
                raise CodeSafetyError(f"Forbidden import from detected: {mod}")
            if mod and not _is_import_allowed(mod):
                raise CodeSafetyError(f"Import not allowed by policy: {mod}")

        if isinstance(node, ast.Name) and node.id in FORBIDDEN_BUILTINS:
            raise CodeSafetyError(f"Forbidden builtin usage: {node.id}")

        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                attr_name = func.attr
                if attr_name in FORBIDDEN_ATTRS:
                    raise CodeSafetyError(f"Forbidden attribute call detected: .{attr_name}()")
            elif isinstance(func, ast.Name):
                if func.id in FORBIDDEN_BUILTINS:
                    raise CodeSafetyError(f"Forbidden function call detected: {func.id}()")

    if sys.version_info >= (3, 8):
        pass
    else:
        pass
