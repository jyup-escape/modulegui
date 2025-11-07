import shutil
from pathlib import Path
from PyQt6.QtWidgets import QMessageBox, QInputDialog
from .python_manager import PythonManager
from .utils import run_command, get_python_path

class EnvManager:
    def __init__(self, env_root: Path):
        self.env_root = env_root
        self.env_root.mkdir(parents=True, exist_ok=True)
        self.python_mgr = PythonManager()

    def discover(self):
        envs = []
        if self.env_root.exists():
            for p in self.env_root.iterdir():
                if (p / "pyvenv.cfg").exists():
                    envs.append(p)
        envs.sort(key=lambda p: p.name)
        return envs

    def create(self, name):
        if not name:
            QMessageBox.warning(None, "入力エラー", "環境名を入力してください。")
            return
        env_path = self.env_root / name
        run_command(["uv", "venv", str(env_path)])
        QMessageBox.information(None, "完了", f"環境 {name} を作成しました。")

    def delete(self, path: Path):
        if path.parent != self.env_root:
            QMessageBox.warning(None, "注意", "管理対象外の環境は削除できません。")
            return
        ret = QMessageBox.question(None, "確認", f"環境「{path.name}」を削除しますか？")
        if ret != QMessageBox.StandardButton.Yes:
            return
        shutil.rmtree(path)
        QMessageBox.information(None, "削除完了", f"{path.name} を削除しました。")

    def change_python_version(self, env_path: Path):
        dlg = QInputDialog()
        dlg.setWindowTitle("Python バージョン変更")
        dlg.setLabelText("変更後の Python バージョンを入力（例: 3.11）:")
        if not dlg.exec():
            return
        ver = dlg.textValue().strip()
        resolved = self.python_mgr.resolve_version(ver)
        if not resolved:
            QMessageBox.warning(None, "注意", f"バージョン {ver} は見つかりません。")
            return

        py = get_python_path(env_path)
        req = env_path / "requirements.txt"
        proc = run_command(["uv", "pip", "freeze", "--python", str(py)])
        req.write_text(proc.stdout)

        new_env = self.env_root / f"{env_path.name}_py{resolved.replace('.', '')}"
        run_command(["uv", "python", "install", resolved])
        run_command(["uv", "venv", str(new_env), "--python", resolved])

        new_py = get_python_path(new_env)
        run_command(["uv", "pip", "install", "-r", str(req), "--python", str(new_py)])
        QMessageBox.information(None, "完了", f"{new_env.name} を作成しました。")
