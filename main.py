import sys
import json
import subprocess
import shutil
import re
from pathlib import Path
from managepython import PythonManager
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
    QGroupBox,
    QHeaderView,
    QAbstractItemView,
)


# -----------------------------------------------------------------------------
# 非同期実行スレッド（※通常のボタン操作はこれでOK。バージョン変更は同期で順序制御）
# -----------------------------------------------------------------------------
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
                    f"Command failed: {' '.join(map(str, self.cmd))}\n{proc.stderr.strip()}"
                )
            self.finished.emit(self.op_name, proc.stdout)
        except Exception as exc:
            self.finished.emit(self.op_name, exc)


# -----------------------------------------------------------------------------
# メインGUI
# -----------------------------------------------------------------------------
class ModuleGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.Pythonmanager = PythonManager()
        self.setWindowTitle("ModuleGUI - モジュールと環境マネージャー")
        self.resize(900, 640)

        self.threads = []
        self.env_root = Path.cwd() / "envs"
        self.env_root.mkdir(parents=True, exist_ok=True)
        self.current_env_path: Path | None = None
        self.modules_cache: list[dict] = []
        self.active_commands = 0

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)
        self.setLayout(layout)

        # ====== 環境管理 ======
        env_group = QGroupBox("環境管理")
        env_group_layout = QVBoxLayout()
        env_group_layout.setSpacing(12)
        env_group.setLayout(env_group_layout)

        hl_env = QHBoxLayout()
        hl_env.setSpacing(10)
        self.env_combo = QComboBox()
        self.env_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        hl_env.addWidget(QLabel("環境"))
        hl_env.addWidget(self.env_combo, 1)

        self.btn_new_env = QPushButton("新規環境作成")
        self.btn_delete_env = QPushButton("環境削除")
        self.btn_refresh_env = QPushButton("環境更新")
        self.btn_updatemodules = QPushButton("一括モジュール更新")
        self.btn_pythonversions = QPushButton("Python バージョン管理")
        self.btn_change_pyver = QPushButton("Python バージョン変更")
        self.btn_change_pyver.setToolTip("選択中の環境を指定Pythonで再構築し、モジュールを引き継ぎます。")

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        for b in (
            self.btn_new_env,
            self.btn_delete_env,
            self.btn_refresh_env,
            self.btn_updatemodules,
            self.btn_pythonversions,
            self.btn_change_pyver,
        ):
            b.setMinimumHeight(32)
            button_row.addWidget(b)

        env_group_layout.addLayout(hl_env)
        env_group_layout.addLayout(button_row)

        self.env_info_label = QLabel("環境が選択されていません。")
        self.env_info_label.setWordWrap(True)
        self.env_info_label.setStyleSheet(
            "QLabel { color: #555; background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 6px; padding: 8px; }"
        )
        env_group_layout.addWidget(self.env_info_label)

        layout.addWidget(env_group)

        # ====== モジュール管理 ======
        modules_group = QGroupBox("モジュール管理")
        modules_layout = QVBoxLayout()
        modules_layout.setSpacing(12)
        modules_group.setLayout(modules_layout)

        self.module_summary_label = QLabel("環境を選択するとモジュール一覧を表示します。")
        modules_layout.addWidget(self.module_summary_label)

        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("モジュール名を検索…")
        self.search_input.setClearButtonEnabled(True)
        self.btn_clear_search = QPushButton("検索クリア")
        self.btn_clear_search.setMinimumWidth(100)
        self.btn_clear_search.setEnabled(False)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.btn_clear_search)
        modules_layout.addLayout(search_layout)

        self.table = QTableWidget(0, 3)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setHorizontalHeaderLabels(["モジュール名", "バージョン", "操作"])
        modules_layout.addWidget(self.table, 1)

        hl_add = QHBoxLayout()
        hl_add.setSpacing(8)
        self.input_pkg = QLineEdit()
        self.input_pkg.setPlaceholderText("モジュール名を入力…")
        self.input_pkg.setClearButtonEnabled(True)
        self.btn_install = QPushButton("インストール")
        self.btn_install.setToolTip("入力したモジュールを現在の環境にインストールします。")
        hl_add.addWidget(self.input_pkg)
        hl_add.addWidget(self.btn_install)
        modules_layout.addLayout(hl_add)

        layout.addWidget(modules_group, 1)

        # ====== ステータスバー ======
        self.status = QStatusBar()
        self.status.setSizeGripEnabled(False)
        layout.addWidget(self.status)

        # 操作対象まとめ
        self._interactive_widgets = [
            self.btn_new_env,
            self.btn_delete_env,
            self.btn_refresh_env,
            self.btn_updatemodules,
            self.btn_pythonversions,
            self.btn_change_pyver,
            self.btn_install,
            self.input_pkg,
            self.search_input,
            self.btn_clear_search,
        ]

        # つなぎこみ
        self.btn_refresh_env.clicked.connect(self.load_environments)
        self.btn_new_env.clicked.connect(self.create_environment)
        self.btn_delete_env.clicked.connect(self.delete_environment)
        self.env_combo.currentIndexChanged.connect(self.on_env_changed)
        self.btn_updatemodules.clicked.connect(self.update_modules)
        self.btn_install.clicked.connect(self.install_module)
        self.btn_pythonversions.clicked.connect(self.Pythonmanager.manage_python_versions)
        self.btn_change_pyver.clicked.connect(self.change_env_python_version)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.btn_clear_search.clicked.connect(self.clear_search)

        self.load_environments()

    # =========================================================================
    # 追加: バージョン厳密解決
    # =========================================================================
    def _resolve_python_version(self, user_input: str) -> str | None:
        """
        uv python list の出力から 3.x[.y] の数値だけを抽出し、入力に最も合致するものを返す。
        完全一致 > "3.11" のようにマイナーのみ → その系の最大パッチ。
        """
        try:
            proc = subprocess.run(["uv", "python", "list"], capture_output=True, text=True, check=True)
            lines = proc.stdout.strip().splitlines()
        except Exception as exc:
            QMessageBox.critical(self, "エラー", f"'uv python list' の取得に失敗しました。\n{exc}")
            return None

        versions = []
        for l in lines:
            m = re.search(r"\b3\.\d+(?:\.\d+)?\b", l)
            if m:
                versions.append(m.group(0))

        if not versions:
            return None

        # 完全一致
        if user_input in versions:
            return user_input

        # 3.11 → 3.11.x 最大パッチ
        if user_input.count(".") == 1:
            prefix = user_input + "."
            cands = [v for v in versions if v.startswith(prefix)]
            if cands:
                def pnum(v: str) -> int:
                    try:
                        return int(v.split(".")[2])
                    except Exception:
                        return -1
                cands.sort(key=pnum, reverse=True)
                return cands[0]
        return None

    # =========================================================================
    # 追加: バージョン変更（同期で順序制御 / Windowsパス考慮）
    # =========================================================================
    def change_env_python_version(self):
        if not self.current_env_path:
            QMessageBox.warning(self, "注意", "先に環境を選択してください。")
            return

        # 候補を見せる（取得失敗しても入力は可能）
        versions_text = ""
        try:
            proc = subprocess.run(["uv", "python", "list"], capture_output=True, text=True)
            cand = [m.group(0) for l in proc.stdout.splitlines() if (m := re.search(r"\b3\.\d+(?:\.\d+)?\b", l))]
            versions_text = "\n".join(f"  • {v}" for v in cand) if cand else "(取得失敗)"
        except Exception:
            versions_text = "(取得失敗)"

        dlg = QInputDialog(self)
        dlg.setWindowTitle("Python バージョン変更")
        dlg.setLabelText(f"利用可能候補:\n{versions_text}\n\n変更後のPythonバージョン（例: 3.11 / 3.11.9）:")
        dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        dlg.resize(500, 260)
        if not dlg.exec():
            return
        vin = dlg.textValue().strip()
        if not vin:
            return

        resolved = self._resolve_python_version(vin)
        if not resolved:
            QMessageBox.warning(self, "未検出", f"指定バージョン「{vin}」は見つかりません。")
            return

        # freeze
        cur_py = self.get_current_python()
        if not cur_py:
            QMessageBox.critical(self, "エラー", "現在の環境のPython実行ファイルが見つかりません。")
            return

        tmp_req = self.current_env_path / "_tmp_requirements_for_migration.txt"
        self.set_status("既存モジュールをfreeze中…")
        proc_f = subprocess.run(["uv", "pip", "freeze", "--python", str(cur_py)],
                                capture_output=True, text=True)
        if proc_f.returncode != 0:
            QMessageBox.critical(self, "エラー", f"freezeに失敗しました。\n{proc_f.stderr}")
            return
        tmp_req.write_text(proc_f.stdout, encoding="utf-8")

        # 新環境名（安全のため別フォルダ）
        suffix = resolved.replace(".", "")
        new_env = self.env_root / f"{self.current_env_path.name}_py{suffix}"
        if new_env.exists():
            ret = QMessageBox.question(self, "上書き確認", f"{new_env} は既に存在します。削除して作り直しますか？")
            if ret != QMessageBox.StandardButton.Yes:
                return
            try:
                shutil.rmtree(new_env)
            except Exception as exc:
                QMessageBox.critical(self, "エラー", f"既存環境の削除に失敗しました。\n{exc}")
                return

        # 1) Python 本体インストール（同期）
        self.set_status(f"Python {resolved} をインストール中…")
        p1 = subprocess.run(["uv", "python", "install", resolved], capture_output=True, text=True)
        if p1.returncode != 0:
            QMessageBox.critical(self, "エラー", f"Pythonインストールに失敗しました。\n{p1.stderr}")
            return

        # 2) venv 作成（同期）
        self.set_status(f"新環境 {new_env.name} を構築中…")
        p2 = subprocess.run(["uv", "venv", str(new_env), "--python", resolved], capture_output=True, text=True)
        if p2.returncode != 0:
            QMessageBox.critical(self, "エラー", f"環境作成に失敗しました。\n{p2.stderr}")
            return

        # 3) 新環境の python.exe / bin/python を確認
        new_py = new_env / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
        if not new_py.exists():
            # uv venv直後に遅延することがあるので、念のため再確認
            try:
                new_py.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            if not new_py.exists():
                QMessageBox.critical(self, "エラー", f"新しいPythonが見つかりません: {new_py}")
                return

        # 4) 引継ぎインストール（同期）
        self.set_status("モジュールを新環境へインストール中…（時間がかかる場合があります）")
        p3 = subprocess.run(
            ["uv", "pip", "install", "-r", str(tmp_req), "--python", str(new_py)],
            capture_output=True, text=True
        )
        if p3.returncode != 0:
            QMessageBox.critical(self, "エラー", f"モジュール引継ぎに失敗しました。\n{p3.stderr}")
            return

        QMessageBox.information(self, "完了", f"Python {resolved} の環境を作成しました。\n{new_env}")
        self.load_environments()

    # =========================================================================
    # 以下、既存の操作（そのまま）
    # =========================================================================
    def install_module(self):
        pkg_name = self.input_pkg.text().strip()
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

    def update_interaction_state(self):
        busy = self.active_commands > 0
        for w in self._interactive_widgets:
            w.setEnabled(not busy)
        self.env_combo.setEnabled(not busy)
        self.table.setEnabled(not busy)
        self.setCursor(Qt.CursorShape.BusyCursor if busy else Qt.CursorShape.ArrowCursor)

    def on_search_text_changed(self, text: str):
        self.btn_clear_search.setEnabled(bool(text.strip()))
        self.apply_module_filter()

    def clear_search(self):
        if self.search_input.text():
            self.search_input.clear()

    def apply_module_filter(self):
        query = self.search_input.text().strip().lower()
        filtered = []
        for module in self.modules_cache:
            name = module.get("name", "")
            if not query or query in name.lower():
                filtered.append(module)

        self.table.setRowCount(0)
        for pkg in filtered:
            row = self.table.rowCount()
            self.table.insertRow(row)
            pkg_name = pkg.get("name", "")
            self.table.setItem(row, 0, QTableWidgetItem(pkg_name))
            self.table.setItem(row, 1, QTableWidgetItem(pkg.get("version", "")))

            btn_del = QPushButton("削除")
            btn_version = QPushButton("バージョン管理")
            btn_del.setToolTip(f"{pkg_name} をアンインストール")
            btn_version.setToolTip(f"{pkg_name} のバージョンを指定して管理")
            btn_del.clicked.connect(lambda _, name=pkg.get("name", ""): self.uninstall_module(name))
            btn_version.clicked.connect(lambda _, name=pkg.get("name", ""): self.manage_version(name))

            op_container = QHBoxLayout()
            op_container.setContentsMargins(0, 0, 0, 0)
            op_container.setSpacing(6)
            op_widget = QWidget()
            op_widget.setLayout(op_container)
            btn_del.setMinimumHeight(28)
            btn_version.setMinimumHeight(28)
            op_container.addWidget(btn_version)
            op_container.addWidget(btn_del)
            op_container.addStretch()
            self.table.setCellWidget(row, 2, op_widget)

        if self.current_env_path is None and not self.modules_cache:
            self.module_summary_label.setText("環境を選択するとモジュール一覧を表示します。")
            return

        total = len(self.modules_cache)
        if total == 0:
            summary = "モジュールが見つかりませんでした。"
        elif query:
            summary = f"{len(filtered)} / {total} 件を表示中"
        else:
            summary = f"{total} 件のモジュールを表示中"
        self.module_summary_label.setText(summary)

    def update_env_info_label(self):
        if not self.current_env_path:
            self.env_info_label.setText("環境が選択されていません。")
            self.env_info_label.setToolTip("")
            return
        env_path = self.current_env_path
        details = [f"選択中: {env_path}"]
        python_info = self.Pythonmanager._read_python_version(env_path)
        if python_info:
            details.append(f"Python: {python_info}")
        self.env_info_label.setText("\n".join(details))
        self.env_info_label.setToolTip(str(env_path))

    def run_command(self, cmd, op_name):
        thread = CommandThread(cmd, op_name)
        thread.finished.connect(self.on_command_finished)
        thread.finished.connect(lambda *_: self.threads.remove(thread) if thread in self.threads else None)
        self.threads.append(thread)
        self.active_commands += 1
        self.update_interaction_state()
        thread.start()
        self.set_status(f"実行中: {op_name} …")

    # ====== 環境検出/ロード ======
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
            self.modules_cache = []
            self.table.setRowCount(0)
            self.module_summary_label.setText("環境が見つかりませんでした。")
            self.set_status("環境が見つかりませんでした。")
        else:
            current_data = self.env_combo.currentData(Qt.ItemDataRole.UserRole)
            if current_data:
                self.current_env_path = Path(current_data)
                self.load_modules()
        self.update_env_info_label()

    def on_env_changed(self, index):
        env_data = self.env_combo.itemData(index, Qt.ItemDataRole.UserRole)
        if not env_data:
            self.current_env_path = None
            self.modules_cache = []
            self.apply_module_filter()
            self.update_env_info_label()
            return
        path = Path(env_data)
        if not path.exists():
            QMessageBox.warning(self, "注意", f"環境パスが存在しません: {path}")
            self.current_env_path = None
            self.modules_cache = []
            self.apply_module_filter()
            self.update_env_info_label()
            return
        self.current_env_path = path
        self.update_env_info_label()
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
        ret = QMessageBox.question(self, "確認", f"環境「{env_path.name}」を削除しますか？")
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

    # ====== モジュール一覧・更新 ======
    def load_modules(self):
        self.module_summary_label.setText("モジュールを読み込み中…")
        self.table.setRowCount(0)
        self.modules_cache = []
        python_path = self.get_current_python()
        if not python_path:
            self.set_status("Python 実行ファイルが見つかりません。環境を確認してください。")
            return
        cmd = ["uv", "pip", "list", "--format", "json", "--python", str(python_path)]
        self.run_command(cmd, "モジュール一覧取得")

    def populate_module_table(self, modules):
        self.modules_cache = list(modules)
        self.apply_module_filter()

    def manage_version(self, name):
        if not name:
            return
        python_path = self.get_current_python()
        if not python_path:
            QMessageBox.warning(self, "注意", "先に環境を選択してください。")
            return
        version, ok = QInputDialog.getText(
            self, "バージョン管理",
            f"モジュール「{name}」のインストールするバージョンを入力してください（空欄で最新）:"
        )
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
        cmd = ["uv", "pip", "uninstall", "--python", str(python_path), "-y", name]
        self.run_command(cmd, f"モジュール削除 ({name})")

    def on_command_finished(self, op_name, result):
        # 非同期コマンドの完了ハンドリング
        self.active_commands = max(0, self.active_commands - 1)
        self.update_interaction_state()
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

        if op_name.startswith("モジュールインストール") or op_name.startswith("モジュール削除") or op_name.startswith("モジュールバージョン管理"):
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
                    self, "確認",
                    f"{len(modules)}個のモジュールに更新があります。更新しますか？"
                )
                if ret != QMessageBox.StandardButton.Yes:
                    return

                cmd = ["uv", "pip", "install", "--upgrade", "--python", str(python_path)]
                cmd.extend(pkg["name"] for pkg in modules)
                self.run_command(cmd, "モジュール更新")
            except Exception as exc:
                QMessageBox.critical(self, "エラー", f"更新可能モジュール確認に失敗しました。\n{exc}")
                return

        if op_name == "モジュール更新":
            self.set_status(f"{op_name} 完了")
            self.load_modules()
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
