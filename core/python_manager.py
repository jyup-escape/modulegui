import re
from PyQt6.QtWidgets import QMessageBox
from .utils import run_command

class PythonManager:
    """uv を使った Python バージョン管理"""

    def list_versions(self) -> list[str]:
        try:
            proc = run_command(["uv", "python", "list"])
            return sorted(set(re.findall(r"\b3\.\d+(?:\.\d+)?\b", proc.stdout)))
        except Exception:
            return []

    def resolve_version(self, user_input: str) -> str | None:
        versions = self.list_versions()
        if user_input in versions:
            return user_input
        if user_input.count(".") == 1:
            prefix = user_input + "."
            cands = [v for v in versions if v.startswith(prefix)]
            if cands:
                cands.sort(key=lambda v: int(v.split(".")[2]) if len(v.split(".")) > 2 else -1, reverse=True)
                return cands[0]
        return None

    def install(self, version: str):
        try:
            run_command(["uv", "python", "install", version])
        except Exception as e:
            QMessageBox.critical(None, "エラー", f"Python {version} のインストールに失敗しました。\n{e}")

    def show_versions(self):
        versions = self.list_versions()
        if not versions:
            QMessageBox.warning(None, "注意", "Python バージョンが見つかりません。")
        else:
            msg = "\n".join(f"  • {v}" for v in versions)
            QMessageBox.information(None, "利用可能な Python バージョン", msg)
