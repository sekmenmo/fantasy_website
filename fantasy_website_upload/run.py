from __future__ import annotations

import threading
import time
import webbrowser
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def ensure_project_venv() -> None:
    if sys.prefix != sys.base_prefix:
        return
    if os.environ.get("FANTASY_DASHBOARD_NO_VENV_REEXEC"):
        return
    venv_python = ROOT / "backend" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if venv_python.exists():
        os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve())])


def open_browser() -> None:
    from app.config import settings

    time.sleep(1.0)
    url = f"http://{settings.host}:{settings.port}"
    webbrowser.open(url)


if __name__ == "__main__":
    ensure_project_venv()
    sys.path.insert(0, str(ROOT / "backend"))
    from app.config import settings
    import uvicorn

    if settings.should_open_browser:
        threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug and not settings.is_production,
        app_dir="backend",
    )
