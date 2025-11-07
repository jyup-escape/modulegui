import json
from PyQt6.QtWidgets import QMessageBox
from .utils import run_command

class ModuleManager:
    def list(self, python_path):
        try:
            proc = run_command(["uv", "pip", "list", "--format", "json", "--python", str(python_path)])
            return json.loads(proc.stdout)
        except Exception as e:
            QMessageBox.critical(None, "エラー", f"モジュール一覧取得に失敗しました。\n{e}")
            return []

    def install(self, python_path, pkg_name):
        run_command(["uv", "pip", "install", "--python", str(python_path), pkg_name])

    def uninstall(self, python_path, pkg_name):
        run_command(["uv", "pip", "uninstall", "--python", str(python_path), "-y", pkg_name])

    def upgrade_all(self, python_path):
        proc = run_command(["uv", "pip", "list", "--outdated", "--format", "json", "--python", str(python_path)])
        modules = json.loads(proc.stdout)
        if not modules:
            QMessageBox.information(None, "情報", "更新可能なモジュールはありません。")
            return
        names = [m["name"] for m in modules]
        run_command(["uv", "pip", "install", "--upgrade", "--python", str(python_path), *names])
