from __future__ import annotations

import logging
import os
import socket
import sys
from pathlib import Path


def _resource_path(relative_path: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return bundle_root / relative_path


def _available_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    log_dir = Path.home() / "Library" / "Logs" / "Jeff"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "jeff.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    app_script = _resource_path("app.py")
    if not app_script.is_file():
        logging.error("Packaged app.py was not found at %s", app_script)
        return

    config_dir = _resource_path(".streamlit")
    if config_dir.is_dir():
        os.environ["STREAMLIT_CONFIG_DIR"] = str(config_dir)
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    port = _available_local_port()
    smoke_test = os.environ.get("JEFF_PACKAGED_SMOKE_TEST") == "1"
    headless = "true" if smoke_test else "false"
    sys.argv = [
        "streamlit",
        "run",
        str(app_script),
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        f"--server.headless={headless}",
        "--server.fileWatcherType=none",
        "--browser.serverAddress=127.0.0.1",
        "--browser.gatherUsageStats=false",
    ]
    logging.info("Starting Jeff on http://127.0.0.1:%s", port)
    try:
        from streamlit.web.cli import main as streamlit_main

        streamlit_main()
    except Exception:
        logging.exception("Jeff stopped unexpectedly")
        raise


if __name__ == "__main__":
    main()
