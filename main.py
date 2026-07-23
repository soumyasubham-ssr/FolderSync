import ctypes
import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from database import Database
from logger import AppLogger
from sync_engine import SyncEngine
from ui.main_window import MainWindow
if __name__=='__main__':
 ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('com.soumya.foldersync')
 app=QApplication(sys.argv);base=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent));app.setWindowIcon(QIcon(str(base/'icon.ico')));db=Database();db.initialize();log=AppLogger();w=MainWindow(db,log,SyncEngine(db,log));w.show();raise SystemExit(app.exec())
