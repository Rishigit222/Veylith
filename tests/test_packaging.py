from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, (
        f"command failed: {' '.join(cmd)}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    return completed


def test_wheel_includes_static_assets_and_installed_app_serves_them(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    target_dir = tmp_path / "site-packages"
    run_dir = tmp_path / "runtime"
    dist_dir.mkdir()
    target_dir.mkdir()
    run_dir.mkdir()

    _run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(dist_dir), str(REPO_ROOT)],
        cwd=tmp_path,
    )

    wheels = sorted(dist_dir.glob("chronicle_guard-*.whl"))
    assert wheels, f"no wheel built in {dist_dir}"
    wheel_path = wheels[-1]

    with zipfile.ZipFile(wheel_path) as whl:
        names = set(whl.namelist())
    assert "chronicle_guard/static/index.html" in names
    assert "chronicle_guard/static/app.js" in names
    assert "chronicle_guard/static/styles.css" in names

    _run(
        [sys.executable, "-m", "pip", "install", "--target", str(target_dir), str(wheel_path)],
        cwd=tmp_path,
    )

    script = f"""
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from chronicle_guard.app import app

repo_root = Path({str(REPO_ROOT)!r}).resolve()
for entry in sys.path:
    if not entry:
        continue
    resolved = Path(entry).resolve()
    assert resolved != repo_root and repo_root not in resolved.parents, sys.path

client = TestClient(app)
checks = {{
    "/": "<!doctype html>",
    "/static/app.js": "Veylith frontend",
    "/static/styles.css": ":root",
}}
for path, marker in checks.items():
    response = client.get(path)
    assert response.status_code == 200, (path, response.status_code, response.text[:200])
    assert marker in response.text, (path, marker)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(target_dir)
    env["PYTHONNOUSERSITE"] = "1"
    _run([sys.executable, "-c", script], cwd=run_dir, env=env)
