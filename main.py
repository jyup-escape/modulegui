import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QComboBox, QLabel, QStatusBar, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox
)
from PyQt6.QtCore import Qt
from core.env_manager import EnvManager
from core.module_manager import ModuleManager
from core.python_manager import PythonManager
from core.utils import get_python_path

class ModuleGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ModuleGUI - モジュールと環境マネージャー")
        self.resize(900, 640)
        self.env_mgr = EnvManager(Path.cwd() / "envs")
        self.mod_mgr = ModuleManager()
        self.python_mgr = PythonManager()
        self.current_env = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(18)

        # ===== 環境管理 =====
        env_group = QGroupBox("環境管理")
        venv_layout = QVBoxLayout()
        hl = QHBoxLayout()
        self.env_combo = QComboBox()
        hl.addWidget(QLabel("環境"))
        hl.addWidget(self.env_combo, 1)

        self.btn_new = QPushButton("新規環境作成")
        self.btn_del = QPushButton("環境削除")
        self.btn_refresh = QPushButton("環境更新")
        self.btn_update = QPushButton("一括モジュール更新")
        self.btn_pyver = QPushButton("Python バージョン管理")
        self.btn_change = QPushButton("Python バージョン変更")

        row = QHBoxLayout()
        for b in (self.btn_new, self.btn_del, self.btn_refresh, self.btn_update, self.btn_pyver, self.btn_change):
            b.setMinimumHeight(32)
            row.addWidget(b)

        venv_layout.addLayout(hl)
        venv_layout.addLayout(row)
        self.env_info = QLabel("環境が選択されていません。")
        self.env_info.setStyleSheet("QLabel { background-color: #000000; border:1px solid #ddd; border-radius:6px; padding:8px; }")
        venv_layout.addWidget(self.env_info)
        env_group.setLayout(venv_layout)
        layout.addWidget(env_group)

        # ===== モジュール管理 =====
        mod_group = QGroupBox("モジュール管理")
        vmod = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("モジュール名を検索…")
        vmod.addWidget(self.search)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["モジュール名", "バージョン", "操作"])
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        vmod.addWidget(self.table)
        hl_add = QHBoxLayout()
        self.input_pkg = QLineEdit()
        self.btn_install = QPushButton("インストール")
        hl_add.addWidget(self.input_pkg)
        hl_add.addWidget(self.btn_install)
        vmod.addLayout(hl_add)
        mod_group.setLayout(vmod)
        layout.addWidget(mod_group, 1)

        self.status = QStatusBar()
        layout.addWidget(self.status)

        # イベント接続
        self.btn_refresh.clicked.connect(self.refresh_envs)
        self.btn_new.clicked.connect(self.create_env)
        self.btn_del.clicked.connect(self.delete_env)
        self.env_combo.currentIndexChanged.connect(self.on_env_changed)
        self.btn_change.clicked.connect(self.change_python)
        self.btn_pyver.clicked.connect(self.python_mgr.show_versions)
        self.btn_install.clicked.connect(self.install_module)
        self.btn_update.clicked.connect(self.upgrade_all)

        self.refresh_envs()

    # ===== ハンドラ =====
    def load_modules(self):
     """現在の環境のモジュール一覧を取得してテーブルに表示"""
     from PyQt6.QtWidgets import QPushButton, QWidget, QHBoxLayout

     if not self.current_env:
        QMessageBox.warning(self, "注意", "先に環境を選択してください。")
        return

     py = get_python_path(self.current_env)
     modules = self.mod_mgr.list(py)

     self.table.setRowCount(0)
     for pkg in modules:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(pkg["name"]))
        self.table.setItem(row, 1, QTableWidgetItem(pkg["version"]))

        btn_del = QPushButton("削除")
        btn_del.clicked.connect(lambda _, name=pkg["name"]: self.uninstall_module(name))

        btn_ver = QPushButton("バージョン管理")
        btn_ver.clicked.connect(lambda _, name=pkg["name"]: self.manage_version(name))

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(btn_ver)
        layout.addWidget(btn_del)

        container = QWidget()
        container.setLayout(layout)
        self.table.setCellWidget(row, 2, container)

    def refresh_envs(self):
        envs = self.env_mgr.discover()
        self.env_combo.clear()
        for e in envs:
            self.env_combo.addItem(e.name, str(e))

    def create_env(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "新規環境作成", "環境名を入力:")
        if ok and name:
            self.env_mgr.create(name)
            self.refresh_envs()

    def delete_env(self):
        from pathlib import Path
        data = self.env_combo.currentData()
        if data:
            self.env_mgr.delete(Path(data))
            self.refresh_envs()

    def on_env_changed(self):
        from pathlib import Path
        data = self.env_combo.currentData()
        if data:
            self.current_env = Path(data)
            self.env_info.setText(f"選択中: {self.current_env}")
            self.load_modules()

    def change_python(self):
        if self.current_env:
            self.env_mgr.change_python_version(self.current_env)
            self.refresh_envs()

    def install_module(self):
        pkg = self.input_pkg.text().strip()
        if not pkg:
            QMessageBox.warning(self, "注意", "モジュール名を入力してください。")
            return
        py = get_python_path(self.current_env)
        self.mod_mgr.install(py, pkg)
        QMessageBox.information(self, "完了", f"{pkg} をインストールしました。")

    def upgrade_all(self):
        py = get_python_path(self.current_env)
        self.mod_mgr.upgrade_all(py)
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = ModuleGUI()
    window.show()
    sys.exit(app.exec())
