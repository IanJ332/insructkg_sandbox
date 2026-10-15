"""Reproducible local commands. Never opens a hosted course or invokes paid inference."""

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = [
    shutil.which("docker") or "docker",
    "compose",
    "-f",
    str(ROOT / "infrastructure/compose.yaml"),
]


def get_python():
    if sys.platform == "win32":
        venv_py = ROOT / ".venv/Scripts/python.exe"
    else:
        venv_py = ROOT / ".venv/bin/python"
    return str(venv_py) if venv_py.is_file() else sys.executable


def get_tool(tool_name):
    which = shutil.which(tool_name)
    if which:
        return [which]
    return [get_python(), "-m", tool_name]


def run(command, **kwargs):
    return subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def script(name, *args):
    return run([get_python(), str(ROOT / "scripts" / name), *args])


def prerequisites():
    report = {
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": sys.version.split()[0],
        "tools": {tool: shutil.which(tool) for tool in ["git", "python3", "node", "docker"]},
    }
    for port in [3000, 8080]:
        with socket.socket() as s:
            report[f"port_{port}_listening"] = s.connect_ex(("127.0.0.1", port)) == 0
    (ROOT / "artifacts").mkdir(exist_ok=True)
    (ROOT / "artifacts/environment.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    run(["docker", "info", "--format", "{{.ServerVersion}}"])


def dashboard_start():
    pidfile = ROOT / "artifacts/dashboard.pid"
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 8080)) == 0:
            with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=3) as response:  # nosec B310: fixed loopback.
                health = json.load(response)
            if health.get("service") != "siip-analytics":
                raise RuntimeError("Port 8080 belongs to an unverified service; preserving it")
            print("SIIP dashboard already healthy")
            return
    log = (ROOT / "artifacts/dashboard.log").open("a")
    p = subprocess.Popen(
        [get_python(), str(ROOT / "scripts/dashboard.py")],
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pidfile.write_text(str(p.pid))
    print("Dashboard PID", p.pid)
    for _ in range(30):
        if p.poll() is not None:
            raise RuntimeError("Dashboard exited; inspect artifacts/dashboard.log")
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=1) as response:  # nosec B310: fixed loopback.
                if json.load(response).get("service") == "siip-analytics":
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.25)
    raise RuntimeError("Dashboard readiness timeout")


def dashboard_stop():
    pidfile = ROOT / "artifacts/dashboard.pid"
    if pidfile.exists():
        pid = int(pidfile.read_text().strip())
        # Validate process identity before sending any signal.
        if sys.platform == "win32":
            import signal

            try:
                ps_bin = shutil.which("powershell") or "powershell"
                proc = subprocess.run(  # nosec B607: verified system utility.
                    [
                        ps_bin,
                        "-NoProfile",
                        "-Command",
                        f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').CommandLine",
                    ],
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
                observed = proc.stdout.strip().replace("\\", "/")
                target = str(ROOT / "scripts/dashboard.py").replace("\\", "/")
                if target in observed or "scripts/dashboard.py" in observed:
                    os.kill(pid, signal.SIGTERM)
            except (subprocess.SubprocessError, ProcessLookupError, OSError):
                pass
        else:
            observed = subprocess.run(
                ["/bin/ps", "-p", str(pid), "-o", "command="], text=True, capture_output=True
            ).stdout
            if str(ROOT / "scripts/dashboard.py") in observed:
                import signal

                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        if pidfile.exists():
            pidfile.unlink()


def worker_start():
    pidfile = ROOT / "artifacts/worker.pid"
    (ROOT / "artifacts").mkdir(exist_ok=True)
    if pidfile.exists():
        try:
            old_pid = int(pidfile.read_text().strip())
            if sys.platform == "win32":
                ps_bin = shutil.which("powershell") or "powershell"
                proc = subprocess.run(  # nosec B607
                    [
                        ps_bin,
                        "-NoProfile",
                        "-Command",
                        f"Get-Process -Id {old_pid} -ErrorAction SilentlyContinue",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if proc.returncode == 0:
                    print("SIIP feedback worker already running (PID", old_pid, ")")
                    return
            else:
                os.kill(old_pid, 0)
                print("SIIP feedback worker already running (PID", old_pid, ")")
                return
        except (ValueError, OSError, subprocess.SubprocessError):
            pass

    log = (ROOT / "artifacts/worker.log").open("a")
    p = subprocess.Popen(
        [get_python(), str(ROOT / "scripts/feedback_worker.py"), "--poll-interval", "0.5"],
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pidfile.write_text(str(p.pid))
    print("Feedback worker PID", p.pid)


def worker_stop():
    pidfile = ROOT / "artifacts/worker.pid"
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            if sys.platform == "win32":
                import signal

                try:
                    ps_bin = shutil.which("powershell") or "powershell"
                    proc = subprocess.run(
                        [
                            ps_bin,
                            "-NoProfile",
                            "-Command",
                            f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}').CommandLine",
                        ],
                        text=True,
                        capture_output=True,
                        timeout=5,
                    )
                    observed = proc.stdout.strip().replace("\\", "/")
                    target = str(ROOT / "scripts/feedback_worker.py").replace("\\", "/")
                    if target in observed or "scripts/feedback_worker.py" in observed:
                        os.kill(pid, signal.SIGTERM)
                except (subprocess.SubprocessError, ProcessLookupError, OSError):
                    pass
            else:
                observed = subprocess.run(
                    ["/bin/ps", "-p", str(pid), "-o", "command="], text=True, capture_output=True
                ).stdout
                if str(ROOT / "scripts/feedback_worker.py") in observed:
                    import signal

                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
        except ValueError:
            pass
        if pidfile.exists():
            pidfile.unlink()


def stop_services():
    worker_stop()
    dashboard_stop()
    # The official image starts PostgreSQL as a background process. A container
    # stop alone can leave a socket lock in its writable layer across restarts.
    running = subprocess.run(
        COMPOSE + ["ps", "--status", "running", "-q", "prairielearn"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if running:
        ready = subprocess.run(
            COMPOSE + ["exec", "-T", "prairielearn", "pg_isready", "-q"], cwd=ROOT
        )
        if ready.returncode == 0:
            try:
                run(
                    COMPOSE
                    + [
                        "exec",
                        "-T",
                        "prairielearn",
                        "/PrairieLearn/scripts/start_postgres.sh",
                        "stop",
                    ],
                    timeout=75,
                )
            except subprocess.CalledProcessError:
                pass
    run(COMPOSE + ["stop"])


def tests(pattern=None):
    command = [get_python(), "-m", "unittest", "discover", "-s", "tests", "-v"]
    if pattern:
        command += ["-k", pattern]
    p = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    (ROOT / "artifacts/tests.log").write_text(p.stdout)
    print(p.stdout)
    if p.returncode:
        raise SystemExit(p.returncode)


parser = argparse.ArgumentParser()
parser.add_argument(
    "command",
    choices=[
        "check",
        "install",
        "init",
        "start-pl",
        "start-dashboard",
        "start-worker",
        "stop-worker",
        "start",
        "seed",
        "graph",
        "test-sql",
        "test-feedback",
        "test",
        "evaluate",
        "fresh-preflight",
        "stop",
        "reset",
        "demo",
        "smoke",
        "test-public",
        "test-research",
        "quality",
        "build",
        "e2e",
    ],
)
args = parser.parse_args()
cmd = args.command
if cmd == "check":
    prerequisites()
elif cmd == "install":
    venv_dir = ROOT / ".venv"
    if not venv_dir.exists():
        run([sys.executable, "-m", "venv", str(venv_dir)])
    target_py = get_python()
    run([target_py, "-m", "pip", "install", "-r", "requirements-dev.txt"])
elif cmd == "init":
    for name in ["prepare.py", "expected.py", "graph_audit.py", "seed.py"]:
        script(name)
elif cmd == "start-pl":
    run(COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "300"])
elif cmd == "start-dashboard":
    dashboard_start()
elif cmd == "start-worker":
    worker_start()
elif cmd == "stop-worker":
    worker_stop()
elif cmd == "start":
    run(COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "300"])
    dashboard_start()
    worker_start()
elif cmd == "seed":
    script("seed.py")
elif cmd == "graph":
    script("graph_audit.py")
elif cmd == "test-sql":
    tests("SQLTests")
elif cmd == "test-feedback":
    tests("FeedbackTests")
elif cmd == "test":
    tests()
elif cmd == "test-research":
    run([get_python(), "-m", "unittest", "discover", "-s", "research_tests", "-v"])
elif cmd == "test-public":
    script("init_public.py")
    run(
        [get_python(), "-m", "unittest", "discover", "-s", "tests", "-v"],
        env={**os.environ, "SIIP_DATA_DIR": str(ROOT / "artifacts/public-data")},
    )
elif cmd == "quality":
    run([*get_tool("ruff"), "check", "."])
    run([*get_tool("ruff"), "format", "--check", "."])
    run([*get_tool("mypy")])
    script("validate_config.py")
elif cmd == "build":
    run([get_python(), "-m", "pip", "wheel", "--no-deps", ".", "--wheel-dir", "artifacts/dist"])
    script("check_wheel.py")
elif cmd == "e2e":
    env = dict(os.environ)
    d_cache = Path("D:/AI/Cache/Playwright")
    if d_cache.is_dir() and "PLAYWRIGHT_BROWSERS_PATH" not in env:
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(d_cache)
    run(
        [get_python(), str(ROOT / "tests/e2e/prairielearn_flow.py"), "--ack-local-synthetic"],
        env=env,
    )
elif cmd == "evaluate":
    script("evaluate.py")
elif cmd == "fresh-preflight":
    script("extract.py")
elif cmd == "smoke":
    script("smoke.py")
elif cmd == "stop":
    stop_services()
elif cmd == "reset":
    # Reversible reset: keep all current state in timestamped backups; no volume deletion.
    stop_services()
    saved = ROOT / "artifacts" / ("reset-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    saved.mkdir()
    if (ROOT / "artifacts/synthetic.sqlite3").exists():
        shutil.move(ROOT / "artifacts/synthetic.sqlite3", saved / "synthetic.sqlite3")
    script("seed.py")
    print("Synthetic store reset; prior database saved to", saved)
    print(
        "PrairieLearn history retained. Use Regenerate your assessment instance for a fresh local demo."
    )
elif cmd == "demo":
    script("seed.py")
    script("graph_audit.py")
    script("evaluate.py")
    run(COMPOSE + ["up", "-d", "--wait", "--wait-timeout", "300"])
    dashboard_start()
    worker_start()
    print(
        "Open http://localhost:3000/pl and http://127.0.0.1:8080; follow docs/DEMO.md. UI actions are manual; fixture runs do not prove UI success."
    )
