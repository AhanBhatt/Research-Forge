"""Sandboxed Python execution for lightweight experiments."""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from time import perf_counter

from pydantic import BaseModel


class PythonRunResult(BaseModel):
    """Result of executing a Python snippet in a constrained subprocess."""

    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    duration_seconds: float = 0.0
    blocked_reason: str | None = None


class PythonSandboxRunner:
    """Best-effort secure runner for toy local experiments."""

    BANNED_IMPORTS = {
        "os",
        "sys",
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "shutil",
        "pathlib",
        "ctypes",
        "multiprocessing",
    }
    BANNED_CALLS = {"eval", "exec", "compile", "__import__", "open", "input"}

    def __init__(self, timeout_seconds: int = 20) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, code: str) -> PythonRunResult:
        """Validate and execute code in an isolated temp directory."""

        violation = self._check_safety(code)
        if violation:
            return PythonRunResult(
                ok=False,
                exit_code=1,
                stdout="",
                stderr="",
                blocked_reason=violation,
            )

        start = perf_counter()
        normalized = textwrap.dedent(code).strip() + "\n"
        with tempfile.TemporaryDirectory(prefix="research_forge_") as tmp:
            script_path = Path(tmp) / "experiment.py"
            script_path.write_text(normalized, encoding="utf-8")

            env = {"PYTHONHASHSEED": "0"}
            try:
                proc = subprocess.run(
                    [sys.executable, "-I", str(script_path)],
                    cwd=tmp,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
                duration = perf_counter() - start
                return PythonRunResult(
                    ok=proc.returncode == 0,
                    exit_code=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    duration_seconds=duration,
                )
            except subprocess.TimeoutExpired as exc:
                duration = perf_counter() - start
                return PythonRunResult(
                    ok=False,
                    exit_code=124,
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or "Process timed out",
                    timed_out=True,
                    duration_seconds=duration,
                )

    def _check_safety(self, code: str) -> str | None:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return f"Syntax error in experiment code: {exc.msg}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base = alias.name.split(".")[0]
                    if base in self.BANNED_IMPORTS:
                        return f"Import blocked: {base}"
            if isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                if module in self.BANNED_IMPORTS:
                    return f"Import blocked: {module}"
            if isinstance(node, ast.Call):
                call_name = self._resolve_call_name(node.func)
                if call_name in self.BANNED_CALLS:
                    return f"Call blocked: {call_name}"
        return None

    @staticmethod
    def _resolve_call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""
