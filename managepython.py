import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QInputDialog, QMessageBox
from PyQt6.QtCore import Qt
class PythonManager:
    def manage_python_versions(self):
        dialog = QInputDialog()
        dialog.setLabelText("使用するPython バージョンを入力してください（例: 3.11）:")
        dialog.setWindowTitle("Python バージョン管理")
        dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        dialog.resize(400, 200)
        cmd = ["uv", "python", "list"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            versions = proc.stdout.strip().split('\n')
            formatted_versions = '\n'.join(f"  • {v.strip()}" for v in versions if v.strip())
            message = f"インストール済み/利用可能なPython バージョン:\n{formatted_versions}\n\n使用するPython バージョンを入力してください（例: 3.11）:"
            dialog.setLabelText(message)
        except Exception:
            dialog.setLabelText("使用するPython バージョンを入力してください（例: 3.11）:")

        if not dialog.exec():
            return
        version = dialog.textValue().strip()
        if not version:
            return
        try:
            cmd = ["uv", "python", "install", version]
            self.run_command(cmd, f"Python {version} インストール")
        except Exception as exc:
            QMessageBox.critical(self, "エラー", f"Python {version} のインストールに失敗しました。\n{exc}")
    def _read_python_version(self, env_path: Path) -> str | None:
        pyvenv = env_path / "pyvenv.cfg"
        if not pyvenv.exists():
            return None
        try:
            for line in pyvenv.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.lower().startswith("version ="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            return None
        return None