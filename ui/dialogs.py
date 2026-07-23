from pathlib import Path
from PySide6.QtWidgets import *
from models import FolderPair,SyncMode
class PairDialog(QDialog):
 def __init__(self,parent=None,pair=None):
  super().__init__(parent);self.setWindowTitle('Folder Pair');self.name=QLineEdit(pair.name if pair else '');self.left=QLineEdit(pair.left_path if pair else '');self.right=QLineEdit(pair.right_path if pair else '');self.mode=QComboBox();[self.mode.addItem(x.label,x.value) for x in SyncMode]
  if pair:self.mode.setCurrentIndex(self.mode.findData(pair.mode.value))
  self.enabled=QCheckBox('Enabled');self.enabled.setChecked(pair.enabled if pair else True);l=QVBoxLayout(self);f=QFormLayout();f.addRow('Name',self.name);f.addRow('Left folder',self.row(self.left));f.addRow('Right folder',self.row(self.right));f.addRow('Mode',self.mode);f.addRow('',self.enabled);l.addLayout(f);b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);l.addWidget(b)
 def row(self,e):
  w=QWidget();l=QHBoxLayout(w);b=QPushButton('Browse…');b.clicked.connect(lambda:self.pick(e));l.addWidget(e);l.addWidget(b);return w
 def pick(self,e):e.setText(QFileDialog.getExistingDirectory(self,'Select folder',e.text() or str(Path.home())) or e.text())
 def value(self,id=None):return FolderPair(id,self.name.text(),self.left.text(),self.right.text(),SyncMode(self.mode.currentData()),self.enabled.isChecked())
