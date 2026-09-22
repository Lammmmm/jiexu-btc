import json
import os
import subprocess
import time
from pathlib import Path
from scripts import launch


def test_running_app_is_reused(monkeypatch, tmp_path):
    monkeypatch.setattr(launch, "LOG_DIR", tmp_path)
    monkeypatch.setattr(launch, "is_ready", lambda url: True)
    def forbidden(*args, **kwargs):
        raise AssertionError("A running app must not spawn another server")
    monkeypatch.setattr(launch.subprocess, "Popen", forbidden)
    assert launch.ensure_server() == {"url": "http://127.0.0.1:8000", "reused": True}


def test_startup_waits_for_readiness_and_runs_hidden(monkeypatch, tmp_path):
    monkeypatch.setattr(launch, "LOG_DIR", tmp_path)
    answers = iter([False, False, True])
    monkeypatch.setattr(launch, "is_ready", lambda url: next(answers))
    calls = []
    class Process:
        pid = 12345
        def poll(self): return None
    def spawn(*args, **kwargs):
        calls.append((args, kwargs))
        return Process()
    monkeypatch.setattr(launch.subprocess, "Popen", spawn)
    monkeypatch.setattr(launch.time, "sleep", lambda seconds: None)
    result = launch.ensure_server(port=8001, debug=True, no_sync=True)
    assert not result["reused"]
    assert len(calls) == 1
    kwargs = calls[0][1]
    assert kwargs["env"]["DEBUG_MODE"] == "true"
    assert kwargs["env"]["AUTO_SYNC"] == "false"
    if os.name == "nt":
        assert kwargs["creationflags"] == subprocess.CREATE_NO_WINDOW
    assert json.loads((tmp_path/"desktop-server-8001.json").read_text())["pid"] == 12345


def test_failed_server_is_reported(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setattr(launch, "LOG_DIR", tmp_path)
    monkeypatch.setattr(launch, "is_ready", lambda url: False)
    class Process:
        pid = 1
        def poll(self): return 1
    monkeypatch.setattr(launch.subprocess, "Popen", lambda *a, **k: Process())
    with pytest.raises(RuntimeError, match="Port 8002 may be occupied"):
        launch.ensure_server(port=8002)


def test_main_opens_browser_only_after_server_ready(monkeypatch):
    events = []
    def ensure(*args):
        events.append("ready")
        return {"url": "http://127.0.0.1:8000", "reused": True}
    monkeypatch.setattr(launch, "ensure_server", ensure)
    monkeypatch.setattr(launch.webbrowser, "open", lambda *a, **k: events.append("browser") or True)
    monkeypatch.setattr(launch.sys, "argv", ["launcher", "-DebugMode"])
    assert launch.main() == 0
    assert events == ["ready", "browser"]
