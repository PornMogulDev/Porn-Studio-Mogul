from pathlib import Path
import subprocess
import sys


def test_production_loop():
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(project_root / "src" / "dev_game.py"), "--smoke"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Production smoke check passed" in result.stdout
