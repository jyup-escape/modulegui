import sys
import json
import subprocess
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QLabel,
    QComboBox,
    QMessageBox,
    QStatusBar,
    QInputDialog,
)


class CommandThread(QThread):
    finished = pyqtSignal(str, object)

    def __init__(self, cmd, op_name):
        super().__init__()
        self.cmd = cmd
        self.op_name = op_name

    def run(self):
        try:
            proc = subprocess.run(self.cmd, capture_output=True, text=True, shell=False)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Command failed: {' '.join(self.cmd)}\n{proc.stderr.strip()}"
                )
            self.finished.emit(self.op_name, proc.stdout)
        except Exception as exc:
            self.finished.emit(self.op_name, exc)


class ModuleGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ModuleGUI - モジュールと環境マネージャー")
        self.resize(800, 600)
        self.threads = []
        self.env_root = Path.cwd() / "envs"
        self.env_root.mkdir(parents=True, exist_ok=True)
        self.current_env_path: Path | None = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Environment controls
        hl_env = QHBoxLayout()
        self.env_combo = QComboBox()
        hl_env.addWidget(QLabel("環境"))
        hl_env.addWidget(self.env_combo)
        self.btn_new_env = QPushButton("新規環境作成")
        self.btn_delete_env = QPushButton("環境削除")
        self.btn_refresh_env = QPushButton("環境更新")
        self.btn_updatemodules = QPushButton("一括モジュール更新")
        hl_env.addWidget(self.btn_new_env)
        hl_env.addWidget(self.btn_delete_env)
        hl_env.addWidget(self.btn_refresh_env)
        hl_env.addWidget(self.btn_updatemodules)
        layout.addLayout(hl_env)

        # Package table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["モジュール名", "バージョン", "操作",])
        layout.addWidget(self.table)

        # Install controls
        hl_add = QHBoxLayout()
        self.input_pkg = QLineEdit()
        self.input_pkg.setPlaceholderText("モジュール名を入力…")
        self.btn_install = QPushButton("インストール")
        hl_add.addWidget(self.input_pkg)
        hl_add.addWidget(self.btn_install)
        layout.addLayout(hl_add)

        self.status = QStatusBar()
        layout.addWidget(self.status)

        self.btn_refresh_env.clicked.connect(self.load_environments)
        self.btn_new_env.clicked.connect(self.create_environment)
        self.btn_delete_env.clicked.connect(self.delete_environment)
        self.env_combo.currentIndexChanged.connect(self.on_env_changed)
        self.btn_updatemodules.clicked.connect(self.update_modules)
        self.btn_install.clicked.connect(self.install_module)
        self.load_environments()
    def install_module(self):
        pkg_name = self.input_pkg.text()
        if not pkg_name:
            QMessageBox.warning(self, "入力エラー", "インストールするモジュール名を入力してください。")
            return
        python_path = self.get_current_python()
        if not python_path:
            QMessageBox.warning(self, "注意", "先に環境を選択してください。")
            return
        cmd = ["uv", "pip", "install", "--python", str(python_path), pkg_name]
        self.run_command(cmd, f"モジュールインストール ({pkg_name})")
    def set_status(self, message: str) -> None:
        self.status.showMessage(message, 5000)

    def run_command(self, cmd, op_name):
        thread = CommandThread(cmd, op_name)
        thread.finished.connect(self.on_command_finished)
        thread.finished.connect(lambda *_: self.threads.remove(thread) if thread in self.threads else None)
        self.threads.append(thread)
        thread.start()
        self.set_status(f"実行中: {op_name} …")

    # Environment management -------------------------------------------------
    def discover_environments(self) -> list[Path]:
        envs: list[Path] = []
        candidates = []
        project_root = Path.cwd()
        default_env = project_root / ".venv"
        if (default_env / "pyvenv.cfg").exists():
            candidates.append(default_env)
        if self.env_root.exists():
            candidates.extend(p for p in self.env_root.iterdir() if p.is_dir())
        seen: set[str] = set()
        for path in candidates:
            pyvenv = path / "pyvenv.cfg"
            if not pyvenv.exists():
                continue
            try:
                key = str(pyvenv.resolve())
            except Exception:
                key = str(pyvenv)
            if key in seen:
                continue
            seen.add(key)
            envs.append(path)
        envs.sort(key=lambda p: p.name.lower())
        return envs

    def load_environments(self):
        environments = self.discover_environments()
        previous = self.env_combo.currentData(Qt.ItemDataRole.UserRole)
        self.env_combo.blockSignals(True)
        self.env_combo.clear()
        for env_path in environments:
            display = env_path.name if env_path.parent == self.env_root else str(env_path)
            self.env_combo.addItem(display, str(env_path))
        self.env_combo.blockSignals(False)

        if previous:
            index = self.env_combo.findData(previous)
            if index >= 0:
                self.env_combo.setCurrentIndex(index)

        if self.env_combo.count() == 0:
            self.current_env_path = None
            self.table.setRowCount(0)
            self.set_status("環境が見つかりませんでした。")
        else:
            current_data = self.env_combo.currentData(Qt.ItemDataRole.UserRole)
            if current_data:
                self.current_env_path = Path(current_data)
                self.load_modules()

    def on_env_changed(self, index):
        env_data = self.env_combo.itemData(index, Qt.ItemDataRole.UserRole)
        if not env_data:
            self.current_env_path = None
            self.table.setRowCount(0)
            return
        path = Path(env_data)
        if not path.exists():
            QMessageBox.warning(self, "注意", f"環境パスが存在しません: {path}")
            self.current_env_path = None
            self.table.setRowCount(0)
            return
        self.current_env_path = path
        self.load_modules()

    def create_environment(self):
        name, ok = QInputDialog.getText(self, "新規環境作成", "環境名を入力してください:")
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, "入力エラー", "環境名を入力してください。")
            return
        if any(ch in name for ch in "\\/:*?\"<>|"):
            QMessageBox.warning(self, "入力エラー", "フォルダー名に使用できない文字が含まれています。")
            return
        env_path = self.env_root / name
        cmd = ["uv", "venv", str(env_path)]
        self.run_command(cmd, f"新規環境作成 ({name})")

    def delete_environment(self):
        env_data = self.env_combo.currentData(Qt.ItemDataRole.UserRole)
        if not env_data:
            QMessageBox.warning(self, "注意", "削除する環境を選択してください。")
            return
        env_path = Path(env_data)
        if env_path.parent != self.env_root:
            QMessageBox.warning(self, "注意", "この環境は管理対象外の場所にあるため削除できません。")
            return
        ret = QMessageBox.question(
            self,
            "確認",
            f"環境「{env_path.name}」を削除しますか？",
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.rmtree(env_path)
        except Exception as exc:
            QMessageBox.critical(self, "エラー", f"環境の削除に失敗しました。\n{exc}")
            return
        self.set_status("環境削除 完了")
        self.load_environments()

    def get_current_python(self) -> Path | None:
        if not self.current_env_path:
            return None
        if sys.platform.startswith("win"):
            candidate = self.current_env_path / "Scripts" / "python.exe"
        else:
            candidate = self.current_env_path / "bin" / "python"
        if not candidate.exists():
            return None
        return candidate

    # Package management -----------------------------------------------------
    def load_modules(self):
        python_path = self.get_current_python()
        if not python_path:
            self.table.setRowCount(0)
            self.set_status("Python 実行ファイルが見つかりません。環境を確認してください。")
            return
        cmd = ["uv", "pip", "list", "--format", "json", "--python", str(python_path)]
        self.run_command(cmd, "モジュール一覧取得")


    def populate_module_table(self, modules):
        self.table.setRowCount(0)
        for pkg in modules:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(pkg.get("name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(pkg.get("version", "")))
            btn_del = QPushButton("削除")
            btn_version = QPushButton("バージョン管理")
            btn_del.clicked.connect(lambda _, name=pkg.get("name", ""): self.uninstall_module(name))
            btn_version.clicked.connect(lambda _, name=pkg.get("name", ""): self.manage_version(name))
            self.table.setCellWidget(row, 2, btn_del)
    def manage_version(self, name):
        if not name:
            return
        python_path = self.get_current_python()
        if not python_path:
            QMessageBox.warning(self, "注意", "先に環境を選択してください。")
            return
        version, ok = QInputDialog.getText(self, "バージョン管理", f"モジュール「{name}」のインストールするバージョンを入力してください（空欄で最新バージョン）:")
        if not ok:
            return
        version = version.strip()
        pkg_spec = f"{name}=={version}" if version else name
        cmd = ["uv", "pip", "install", "--python", str(python_path), pkg_spec]
        self.run_command(cmd, f"モジュールバージョン管理 ({name})")
    def uninstall_module(self, name):
        if not name:
            return
        python_path = self.get_current_python()
        if not python_path:
            QMessageBox.warning(self, "注意", "先に環境を選択してください。")
            return
        ret = QMessageBox.question(self, "確認", f"モジュール「{name}」をアンインストールしますか？")
        if ret != QMessageBox.StandardButton.Yes:
            return
        cmd = ["uv", "pip", "uninstall", name] #問題のゴミ
        self.run_command(cmd, f"モジュール削除 ({name})")

    # Command completion -----------------------------------------------------
    def on_command_finished(self, op_name, result):
        if isinstance(result, Exception):
            QMessageBox.critical(self, "エラー", f"{op_name} に失敗しました。\n{result}")
            self.set_status(f"{op_name} 失敗")
            return

        if op_name == "モジュール一覧取得":
            try:
                modules = json.loads(result or "[]")
            except Exception as exc:
                QMessageBox.critical(self, "エラー", f"モジュール一覧の読み込みに失敗しました。\n{exc}")
                return
            self.populate_module_table(modules)
            self.set_status(f"{op_name} 完了")
            return

        if op_name.startswith("新規環境作成"):
            self.set_status(f"{op_name} 完了")
            self.load_environments()
            return

        if op_name.startswith("モジュールインストール") or op_name.startswith("モジュール削除"):
            self.set_status(f"{op_name} 完了")
            self.load_modules()
            return

        if op_name == "更新可能なモジュール確認":
            try:
                modules = json.loads(result or "[]")
                if not modules:
                    QMessageBox.information(self, "情報", "更新可能なモジュールはありません。")
                    self.set_status("更新確認 完了")
                    return
                
                python_path = self.get_current_python()
                if not python_path:
                    return
                
                ret = QMessageBox.question(
                    self,
                    "確認",
                    f"{len(modules)}個のモジュールに更新可能なバージョンがあります。更新しますか？",
                )
                if ret != QMessageBox.StandardButton.Yes:
                    return
                
                cmd = ["uv", "pip", "install", "--upgrade", "--python", str(python_path)]
                cmd.extend(pkg["name"] for pkg in modules)
                self.run_command(cmd, "モジュール更新")
            except Exception as exc:
                QMessageBox.critical(self, "エラー", f"更新可能なモジュールの確認に失敗しました。\n{exc}")
                return

        self.set_status(f"{op_name} 完了")
    def update_modules(self):    
        python_path = self.get_current_python()
        if not python_path:
            QMessageBox.warning(self, "注意", "先に環境を選択してください。")
            return
        cmd = ["uv", "pip", "list", "--outdated", "--format", "json", "--python", str(python_path)]
        self.run_command(cmd, "更新可能なモジュール確認")
# ========================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModuleGUI()
    window.show()
    sys.exit(app.exec())
