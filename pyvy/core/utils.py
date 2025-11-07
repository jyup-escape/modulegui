import sys
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox

def run_command(cmd: list[str], capture_output=True):
    """サブプロセス実行（例外付き）"""
    try:
        return subprocess.run(cmd, capture_output=capture_output, text=True, check=True)
    except subprocess.CalledProcessError as e:
        QMessageBox.critical(None, "エラー", f"コマンド実行に失敗しました:\n{' '.join(cmd)}\n{e.stderr}")
        raise

def get_python_path(env_path: Path | None) -> Path | None:
    if not env_path:
        return None
    return env_path / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
