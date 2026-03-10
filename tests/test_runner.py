from tools.python_runner import PythonSandboxRunner


def test_runner_executes_safe_code() -> None:
    runner = PythonSandboxRunner(timeout_seconds=5)
    result = runner.run("print('ok')")
    assert result.ok
    assert "ok" in result.stdout


def test_runner_blocks_dangerous_import() -> None:
    runner = PythonSandboxRunner(timeout_seconds=5)
    result = runner.run("import os\nprint('bad')")
    assert not result.ok
    assert "Import blocked" in (result.blocked_reason or "")
