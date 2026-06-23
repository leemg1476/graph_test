from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    ui_path = Path(__file__).with_name("ui.py")
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(ui_path),
                "--server.address",
                "127.0.0.1",
                "--server.port",
                "8501",
            ]
        )
    )


if __name__ == "__main__":
    main()
