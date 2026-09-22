"""Desktop launcher: open the UI, reusing an existing healthy local server."""
import argparse
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "artifacts"
OPENER = build_opener(ProxyHandler({}))  # localhost must not go through a system proxy


def is_ready(url):
    try:
        with OPENER.open(url + "/api/config", timeout=1) as response:
            config = json.load(response)
        return (config.get("symbol") == "BTCUSDT"
                and config.get("timezone") == "Asia/Shanghai"
                and config.get("calendar", {}).get("source") == "https://github.com/6tail/lunar-python")
    except (OSError, URLError, ValueError, AttributeError):
        return False


@contextmanager
def startup_lock(port):
    """Serialize simultaneous double-clicks, automatically released on exit."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / f"launcher-{port}.lock").open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            deadline = time.monotonic() + 40
            while True:
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Another launch is still in progress. Please retry in a moment.")
                    time.sleep(0.2)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


def ensure_server(port=8000, debug=False, no_sync=False):
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    url = f"http://127.0.0.1:{port}"
    with startup_lock(port):
        if is_ready(url):
            return {"url": url, "reused": True}
        python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.is_file():
            raise RuntimeError("Python environment is missing. Run setup.ps1 first.")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if debug:
            env["DEBUG_MODE"] = "true"
        if no_sync:
            env["AUTO_SYNC"] = "false"
        log_path = LOG_DIR / f"desktop-server-{port}.log"
        with log_path.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(
                [str(python), "-m", "uvicorn", "backend.app:create_app", "--factory",
                 "--host", "127.0.0.1", "--port", str(port)],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if is_ready(url):
                result = {"url": url, "reused": False, "pid": process.pid}
                (LOG_DIR / f"desktop-server-{port}.json").write_text(
                    json.dumps(result), encoding="utf-8")
                return result
            if process.poll() is not None:
                raise RuntimeError(f"Server failed to start. Port {port} may be occupied.\nLog: {log_path}")
            time.sleep(0.25)
        raise RuntimeError(f"Server startup timed out.\nLog: {log_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-Port", type=int, default=8000)
    parser.add_argument("--debug", "-DebugMode", action="store_true")
    parser.add_argument("--no-sync", "-NoSync", action="store_true")
    # Used by automated startup verification; ordinary desktop launches open the page.
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        result = ensure_server(args.port, args.debug, args.no_sync)
        if not args.no_browser:
            if not webbrowser.open(result["url"], new=2):
                raise RuntimeError("The server is ready. Open this address in your browser:\n" + result["url"])
        if sys.stdout is not None:
            print(json.dumps(result))
        return 0
    except Exception as exc:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=LOG_DIR / "launcher-error.log", encoding="utf-8", level=logging.ERROR)
        logging.exception("Desktop launch failed")
        if os.name == "nt" and not args.no_browser:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(exc), "节序 BTC 看盘：启动失败", 0x10)
        elif sys.stderr is not None:
            print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
