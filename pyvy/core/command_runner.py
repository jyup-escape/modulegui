import subprocess
from PyQt6.QtCore import QThread, pyqtSignal

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
                raise RuntimeError(f"Command failed: {' '.join(map(str, self.cmd))}\n{proc.stderr.strip()}")
            self.finished.emit(self.op_name, proc.stdout)
        except Exception as exc:
            self.finished.emit(self.op_name, exc)
