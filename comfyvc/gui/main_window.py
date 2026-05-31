import sys
from pathlib import Path
from typing import Optional, List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QComboBox, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QInputDialog, QMessageBox, QFrame, QScrollArea,
    QApplication, QStatusBar, QToolBar, QSizePolicy, QTextEdit,
    QGroupBox,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QAction, QFontDatabase

from ..repository import Repository, RepositoryError
from ..models import Snapshot, Branch
from ..diff import diff_snapshots, DiffResult, NodeChange

# ------------------------------------------------------------------
# Stylesheet
# ------------------------------------------------------------------

STYLESHEET = """
QMainWindow, QWidget {
    background-color: #141414;
    color: #d4d4d4;
    font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}

QSplitter::handle {
    background-color: #2a2a2a;
    width: 2px;
}

/* Toolbar */
QToolBar {
    background-color: #1a1a1a;
    border-bottom: 1px solid #2a2a2a;
    padding: 4px 8px;
    spacing: 6px;
}
QToolBar QLabel {
    color: #888;
    font-size: 11px;
}

/* Buttons */
QPushButton {
    background-color: #252525;
    color: #d4d4d4;
    border: 1px solid #333;
    border-radius: 4px;
    padding: 5px 12px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #2e2e2e;
    border-color: #555;
}
QPushButton:pressed {
    background-color: #1a1a1a;
}
QPushButton#primary {
    background-color: #1e3a5f;
    border-color: #2a6496;
    color: #7eb8f7;
}
QPushButton#primary:hover {
    background-color: #254d7a;
}
QPushButton#danger {
    background-color: #3a1e1e;
    border-color: #6b2c2c;
    color: #f07070;
}
QPushButton#danger:hover {
    background-color: #4a2424;
}

/* Combo box */
QComboBox {
    background-color: #1e1e1e;
    color: #d4d4d4;
    border: 1px solid #333;
    border-radius: 4px;
    padding: 4px 8px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e1e;
    border: 1px solid #444;
    selection-background-color: #1e3a5f;
}

/* List widget */
QListWidget {
    background-color: #181818;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    outline: none;
}
QListWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #222;
}
QListWidget::item:hover {
    background-color: #222;
}
QListWidget::item:selected {
    background-color: #1e3a5f;
    color: #7eb8f7;
}

/* Labels */
QLabel#section-title {
    color: #888;
    font-size: 10px;
    letter-spacing: 1px;
    padding: 8px 0 4px 0;
}
QLabel#branch-indicator {
    color: #7eb8f7;
    font-size: 11px;
}
QLabel#workflow-path {
    color: #666;
    font-size: 10px;
}

/* Diff viewer sections */
QFrame#diff-added {
    background-color: #0d1f0d;
    border: 1px solid #1a3a1a;
    border-radius: 4px;
}
QFrame#diff-removed {
    background-color: #1f0d0d;
    border: 1px solid #3a1a1a;
    border-radius: 4px;
}
QFrame#diff-modified {
    background-color: #1a1a0d;
    border: 1px solid #3a3a1a;
    border-radius: 4px;
}

/* Status bar */
QStatusBar {
    background-color: #1a1a1a;
    border-top: 1px solid #2a2a2a;
    color: #666;
    font-size: 11px;
}

/* Scroll area */
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:vertical {
    background: #1a1a1a;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #333;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #444;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QGroupBox {
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
    color: #666;
    font-size: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
"""


# ------------------------------------------------------------------
# Snapshot list item widget
# ------------------------------------------------------------------

class SnapshotItem(QListWidgetItem):
    def __init__(self, snapshot: Snapshot, is_head: bool = False):
        super().__init__()
        self.snapshot = snapshot
        ts = snapshot.timestamp.strftime("%b %d %H:%M")
        head_marker = " ◀ HEAD" if is_head else ""
        self.setText(f"[{snapshot.short_id}]  {snapshot.message}{head_marker}\n{ts}  ·  {snapshot.node_count} nodes")
        self.setSizeHint(QSize(0, 54))


# ------------------------------------------------------------------
# Diff Viewer
# ------------------------------------------------------------------

class DiffViewer(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.header = QLabel("Select two snapshots to compare")
        self.header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header.setStyleSheet("color: #555; font-size: 13px; padding: 40px;")
        layout.addWidget(self.header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.hide()
        layout.addWidget(self.scroll)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(8)
        self.scroll.setWidget(self.content)

    def show_diff(self, result: DiffResult):
        # Clear previous content
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        a = result.snapshot_a
        b = result.snapshot_b

        # Header
        header_text = (
            f"<b style='color:#7eb8f7'>[{a.short_id}]</b> {a.message}"
            f"<span style='color:#555'>  →  </span>"
            f"<b style='color:#7eb8f7'>[{b.short_id}]</b> {b.message}"
        )
        lbl = QLabel(header_text)
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        self.content_layout.addWidget(lbl)

        summary = QLabel(result.summary)
        summary.setStyleSheet("color: #888; font-size: 11px; padding-bottom: 6px;")
        self.content_layout.addWidget(summary)

        if not result.has_changes:
            no_change = QLabel("These snapshots are identical.")
            no_change.setStyleSheet("color: #555; padding: 20px;")
            no_change.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(no_change)
        else:
            if result.added_nodes:
                self._add_section("ADDED NODES", result.added_nodes, "#4caf50", "diff-added",
                                  lambda n: f"+ {n.get('type', 'Unknown')}  (id: {n.get('id', '?')})")
            if result.removed_nodes:
                self._add_section("REMOVED NODES", result.removed_nodes, "#f44336", "diff-removed",
                                  lambda n: f"- {n.get('type', 'Unknown')}  (id: {n.get('id', '?')})")
            if result.modified_nodes:
                self._add_modified_section(result.modified_nodes)
            if result.added_links or result.removed_links:
                self._add_link_section(result)

        self.content_layout.addStretch()
        self.header.hide()
        self.scroll.show()

    def clear(self):
        self.scroll.hide()
        self.header.show()

    def _add_section(self, title, items, color, frame_id, label_fn):
        group = QGroupBox(f"{title}  ({len(items)})")
        group.setStyleSheet(f"QGroupBox {{ color: {color}; border-color: {color}22; }}")
        vbox = QVBoxLayout(group)
        vbox.setSpacing(4)
        for item in items:
            row = QLabel(label_fn(item))
            row.setStyleSheet(f"color: {color}; padding: 2px 4px;")
            row.setWordWrap(True)
            vbox.addWidget(row)
        self.content_layout.addWidget(group)

    def _add_modified_section(self, nodes: List[NodeChange]):
        group = QGroupBox(f"MODIFIED NODES  ({len(nodes)})")
        group.setStyleSheet("QGroupBox { color: #ffc107; border-color: #ffc10722; }")
        vbox = QVBoxLayout(group)
        vbox.setSpacing(6)
        for node in nodes:
            node_lbl = QLabel(f"~ {node.node_type}  (id: {node.node_id})")
            node_lbl.setStyleSheet("color: #ffc107;")
            vbox.addWidget(node_lbl)
            for field, (before, after) in node.changes.items():
                change_lbl = QLabel(
                    f"  <span style='color:#888'>{field}:</span>"
                    f"  <span style='color:#f07070'>{_fmt(before)}</span>"
                    f"  <span style='color:#555'>→</span>"
                    f"  <span style='color:#7ed87e'>{_fmt(after)}</span>"
                )
                change_lbl.setTextFormat(Qt.TextFormat.RichText)
                change_lbl.setWordWrap(True)
                change_lbl.setIndent(12)
                vbox.addWidget(change_lbl)
        self.content_layout.addWidget(group)

    def _add_link_section(self, result: DiffResult):
        parts = []
        for l in result.added_links:
            parts.append(f"<span style='color:#4caf50'>+</span> {_link_str(l)}")
        for l in result.removed_links:
            parts.append(f"<span style='color:#f44336'>-</span> {_link_str(l)}")
        total = len(result.added_links) + len(result.removed_links)
        group = QGroupBox(f"CONNECTIONS  ({total})")
        group.setStyleSheet("QGroupBox { color: #888; border-color: #33333388; }")
        vbox = QVBoxLayout(group)
        for p in parts:
            lbl = QLabel(p)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            vbox.addWidget(lbl)
        self.content_layout.addWidget(group)


def _fmt(val) -> str:
    s = str(val)
    return s[:60] + "…" if len(s) > 60 else s


def _link_str(link) -> str:
    if isinstance(link, list) and len(link) >= 5:
        return f"node {link[1]}[{link[2]}] → node {link[3]}[{link[4]}]"
    return str(link)


# ------------------------------------------------------------------
# Main Window
# ------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.repo: Optional[Repository] = None
        self.workflow_path: Optional[str] = None
        self.selected_snapshots: List[Snapshot] = []

        self.setWindowTitle("ComfyVC — Workflow Version Control")
        self.setMinimumSize(1000, 640)
        self.setStyleSheet(STYLESHEET)

        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)

        open_action = QAction("📂  Open Workflow", self)
        open_action.triggered.connect(self._open_workflow)
        tb.addAction(open_action)

        tb.addSeparator()

        self.workflow_label = QLabel("No workflow open")
        self.workflow_label.setObjectName("workflow-path")
        tb.addWidget(self.workflow_label)

    def _build_central(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # Left panel
        left = QWidget()
        left.setMaximumWidth(320)
        left.setMinimumWidth(220)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(6)

        # Branch controls
        branch_title = QLabel("BRANCH")
        branch_title.setObjectName("section-title")
        left_layout.addWidget(branch_title)

        branch_row = QHBoxLayout()
        self.branch_combo = QComboBox()
        self.branch_combo.currentTextChanged.connect(self._on_branch_changed)
        branch_row.addWidget(self.branch_combo, 1)

        new_branch_btn = QPushButton("+")
        new_branch_btn.setFixedWidth(28)
        new_branch_btn.setToolTip("Create new branch")
        new_branch_btn.clicked.connect(self._create_branch)
        branch_row.addWidget(new_branch_btn)
        left_layout.addLayout(branch_row)

        del_branch_btn = QPushButton("Delete branch")
        del_branch_btn.setObjectName("danger")
        del_branch_btn.clicked.connect(self._delete_branch)
        left_layout.addWidget(del_branch_btn)

        # Snapshot list
        snap_title = QLabel("SNAPSHOTS")
        snap_title.setObjectName("section-title")
        left_layout.addWidget(snap_title)

        self.snapshot_list = QListWidget()
        self.snapshot_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.snapshot_list.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.snapshot_list, 1)

        hint = QLabel("Ctrl+click two snapshots to diff")
        hint.setStyleSheet("color: #444; font-size: 10px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(hint)

        # Action buttons
        self.snapshot_btn = QPushButton("📸  Take Snapshot")
        self.snapshot_btn.setObjectName("primary")
        self.snapshot_btn.clicked.connect(self._take_snapshot)
        self.snapshot_btn.setEnabled(False)
        left_layout.addWidget(self.snapshot_btn)

        self.restore_btn = QPushButton("⏪  Restore Selected")
        self.restore_btn.clicked.connect(self._restore_snapshot)
        self.restore_btn.setEnabled(False)
        left_layout.addWidget(self.restore_btn)

        splitter.addWidget(left)

        # Right panel — diff viewer
        self.diff_viewer = DiffViewer()
        splitter.addWidget(self.diff_viewer)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Open a ComfyUI workflow file to get started")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_workflow(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open ComfyUI Workflow", "", "ComfyUI Workflow (*.json)"
        )
        if not path:
            return

        self.workflow_path = path
        folder = str(Path(path).parent)
        self.repo = Repository(folder)

        try:
            if not self.repo.is_initialized():
                self.repo.init()
            self._refresh_branches()
            self._refresh_snapshots()
            self.snapshot_btn.setEnabled(True)
            self.workflow_label.setText(Path(path).name)
            self.status.showMessage(f"Opened: {path}")
        except RepositoryError as e:
            self._error(str(e))

    def _take_snapshot(self):
        if not self.repo or not self.workflow_path:
            return
        message, ok = QInputDialog.getText(self, "Take Snapshot", "Snapshot message:")
        if not ok or not message.strip():
            return
        try:
            snap = self.repo.take_snapshot(self.workflow_path, message.strip())
            self._refresh_snapshots()
            self.status.showMessage(f"Snapshot [{snap.short_id}] saved — {snap.message}")
        except RepositoryError as e:
            self._error(str(e))

    def _restore_snapshot(self):
        selected = self.snapshot_list.selectedItems()
        if len(selected) != 1:
            self._error("Select exactly one snapshot to restore.")
            return
        snap: Snapshot = selected[0].snapshot
        confirm = QMessageBox.question(
            self, "Restore Snapshot",
            f"Overwrite the current workflow with snapshot [{snap.short_id}]?\n\n{snap.message}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.repo.restore(snap.id, self.workflow_path)
                self.status.showMessage(f"Restored [{snap.short_id}] → {self.workflow_path}")
            except RepositoryError as e:
                self._error(str(e))

    def _create_branch(self):
        if not self.repo:
            return
        name, ok = QInputDialog.getText(self, "New Branch", "Branch name:")
        if not ok or not name.strip():
            return
        try:
            self.repo.create_branch(name.strip())
            self._refresh_branches()
            self.status.showMessage(f"Branch '{name.strip()}' created")
        except RepositoryError as e:
            self._error(str(e))

    def _delete_branch(self):
        if not self.repo:
            return
        name = self.branch_combo.currentText()
        if not name:
            return
        confirm = QMessageBox.question(
            self, "Delete Branch",
            f"Delete branch '{name}'? Snapshots are kept but the branch pointer is removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.repo.delete_branch(name)
                self._refresh_branches()
                self._refresh_snapshots()
                self.status.showMessage(f"Branch '{name}' deleted")
            except RepositoryError as e:
                self._error(str(e))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_branch_changed(self, name: str):
        if not self.repo or not name:
            return
        try:
            self.repo.switch_branch(name)
            self._refresh_snapshots()
            self.diff_viewer.clear()
            self.restore_btn.setEnabled(False)
        except RepositoryError:
            pass

    def _on_selection_changed(self):
        selected = self.snapshot_list.selectedItems()
        count = len(selected)

        self.restore_btn.setEnabled(count == 1)

        if count == 2:
            a = selected[0].snapshot
            b = selected[1].snapshot
            # Show diff with older snapshot first
            if a.timestamp > b.timestamp:
                a, b = b, a
            result = diff_snapshots(a, b)
            self.diff_viewer.show_diff(result)
            self.status.showMessage(result.summary)
        elif count == 1:
            self.diff_viewer.clear()
            snap = selected[0].snapshot
            self.status.showMessage(
                f"[{snap.short_id}] {snap.message}  ·  {snap.timestamp.strftime('%Y-%m-%d %H:%M')}  ·  {snap.node_count} nodes"
            )
        else:
            self.diff_viewer.clear()
            self.status.showMessage("")

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def _refresh_branches(self):
        if not self.repo:
            return
        self.branch_combo.blockSignals(True)
        self.branch_combo.clear()
        current = self.repo.get_current_branch()
        for branch in self.repo.get_branches():
            self.branch_combo.addItem(branch.name)
        idx = self.branch_combo.findText(current)
        if idx >= 0:
            self.branch_combo.setCurrentIndex(idx)
        self.branch_combo.blockSignals(False)

    def _refresh_snapshots(self):
        if not self.repo:
            return
        self.snapshot_list.clear()
        self.diff_viewer.clear()
        try:
            current_branch_name = self.repo.get_current_branch()
            meta_branches = self.repo._read_meta()["branches"]
            head_id = meta_branches.get(current_branch_name, {}).get("head")
            for snap in self.repo.get_snapshots():
                item = SnapshotItem(snap, is_head=(snap.id == head_id))
                self.snapshot_list.addItem(item)
        except RepositoryError as e:
            self.status.showMessage(str(e))

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _error(self, msg: str):
        QMessageBox.critical(self, "Error", msg)
        self.status.showMessage(f"Error: {msg}")
