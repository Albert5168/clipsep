"""Desktop editor: open slides/clippings, edit the separated text, export .pptx."""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np
from PySide6.QtCore import QObject, QRectF, Qt, QThread, Signal
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QIcon, QImage, QKeySequence, QPainter,
                           QPixmap, QTextBlockFormat, QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QDoubleSpinBox, QFileDialog,
                               QFontComboBox, QFormLayout, QGraphicsPixmapItem, QGraphicsScene,
                               QGraphicsTextItem, QGraphicsView, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QProgressDialog, QPushButton, QSplitter, QToolBar, QVBoxLayout,
                               QWidget)

from .core import Block, Page, Run, analyze, load_images
from .export import EMU_PER_PT, LINE_SPACING, SLIDE_W, box_width, export_pptx, line_pitch, text_top

APP_NAME = "剪報圖片文字分離編輯器"
ORG_NAME = "東港養殖研究中心"
DEFAULT_FONT = "Microsoft JhengHei"


def resource(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def to_pixmap(img: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QPixmap.fromImage(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy())


def px_to_pt(page: Page, px: float) -> float:
    return px * SLIDE_W / page.width / EMU_PER_PT


def pt_to_px(page: Page, pt: float) -> float:
    return pt * EMU_PER_PT * page.width / SLIDE_W


# ---------- background processing ----------

class Worker(QObject):
    progress = Signal(int, int, str)
    page_ready = Signal(object)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, paths, drop_watermark, traditional, font):
        super().__init__()
        self.paths, self.drop_watermark, self.traditional, self.font = paths, drop_watermark, traditional, font
        self.cancelled = False

    def run(self):
        try:
            images = []
            for p in self.paths:
                images += [(os.path.basename(p), i, im) for i, im in enumerate(load_images(p), 1)]
            for k, (name, i, im) in enumerate(images):
                if self.cancelled:
                    break
                self.progress.emit(k, len(images), f"{name} 第 {i} 頁")
                page = analyze(im, drop_watermark=self.drop_watermark, traditional=self.traditional)
                for b in page.blocks:
                    b.font = self.font
                self.page_ready.emit(page)
            self.progress.emit(len(images), len(images), "")
        except Exception as e:  # surface any failure to the user instead of dying silently
            self.failed.emit(str(e))
        self.finished.emit()


# ---------- canvas ----------

class TextItem(QGraphicsTextItem):
    def __init__(self, page: Page, block: Block):
        super().__init__()
        self.page, self.block = page, block
        self.setFlags(QGraphicsTextItem.ItemIsMovable | QGraphicsTextItem.ItemIsSelectable
                      | QGraphicsTextItem.ItemIsFocusable)
        self.document().setDocumentMargin(0)
        self.load_block()

    def load_block(self):
        b = self.block
        font = QFont(b.font)
        font.setPixelSize(max(1, round(b.font_px)))
        font.setBold(b.bold)
        self.setFont(font)
        self.setTextWidth(box_width(b))
        doc = self.document()
        doc.clear()
        cur = QTextCursor(doc)
        bf = QTextBlockFormat()
        bf.setLineHeight(line_pitch(b), QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        for i, line in enumerate(b.lines):
            fmt_block = QTextBlockFormat(bf)
            indent = b.indents[i] if i < len(b.indents) else 0
            fmt_block.setLeftMargin(indent)
            if i == 0:
                cur.setBlockFormat(fmt_block)
            else:
                cur.insertBlock(fmt_block)
            for r in line:
                cf = QTextCharFormat()
                cf.setForeground(QBrush(QColor(*r.color)))
                cur.insertText(r.text, cf)
        self.setPos(b.x, text_top(b))

    def save_block(self):
        """Write edits (text, colours, position, font) back into the block."""
        b = self.block
        lines, indents = [], []
        blk = self.document().begin()
        while blk.isValid():
            runs: list[Run] = []
            it = blk.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    c = frag.charFormat().foreground().color()
                    rgb = (c.red(), c.green(), c.blue())
                    for k, part in enumerate(frag.text().split(" ")):
                        if k:  # soft line break -> new line
                            lines.append(runs)
                            indents.append(blk.blockFormat().leftMargin())
                            runs = []
                        if part:
                            if runs and runs[-1].color == rgb:
                                runs[-1].text += part
                            else:
                                runs.append(Run(part, rgb))
                it += 1
            lines.append(runs)
            indents.append(blk.blockFormat().leftMargin())
            blk = blk.next()
        f = self.font()
        b.font = f.family()
        b.font_px = float(f.pixelSize())
        b.bold = f.bold()
        old_top = text_top(b)
        b.lines, b.indents = lines, indents
        b.x = float(self.pos().x())
        b.y += self.pos().y() - old_top

    def mouseDoubleClickEvent(self, event):
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus()
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        c = self.textCursor()
        c.clearSelection()
        self.setTextCursor(c)
        super().focusOutEvent(event)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.isSelected() or self.hasFocus():
            return
        painter.setPen(QColor(0, 160, 255, 90))  # faint outline so boxes are findable
        painter.drawRect(self.boundingRect())


class Canvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setBackgroundBrush(QColor("#3a3f47"))
        self.page: Page | None = None
        self.bg_item: QGraphicsPixmapItem | None = None
        self.show_original = False

    def show_page(self, page: Page | None):
        self.scene().clear()
        self.page, self.bg_item = page, None
        if page is None:
            return
        self.bg_item = self.scene().addPixmap(to_pixmap(page.original if self.show_original else page.background))
        self.bg_item.setZValue(-1)
        for b in page.blocks:
            self.scene().addItem(TextItem(page, b))
        self.scene().setSceneRect(QRectF(0, 0, page.width, page.height))
        self.fit()

    def set_show_original(self, on: bool):
        self.show_original = on
        if self.page is not None and self.bg_item is not None:
            self.bg_item.setPixmap(to_pixmap(self.page.original if on else self.page.background))
            for it in self.text_items():
                it.setVisible(not on)

    def text_items(self) -> list[TextItem]:
        return [i for i in self.scene().items() if isinstance(i, TextItem)]

    def selected_items(self) -> list[TextItem]:
        return [i for i in self.scene().selectedItems() if isinstance(i, TextItem)]

    def sync(self):
        """Save item edits into the page's blocks; drop blocks whose items were deleted."""
        if self.page is None:
            return
        items = self.text_items()
        for it in items:
            it.save_block()
        alive = {id(it.block) for it in items}
        self.page.blocks = [b for b in self.page.blocks if id(b) in alive and any(r.text.strip() for ln in b.lines for r in ln)]

    def fit(self):
        if self.page is not None:
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.fit()


# ---------- main window ----------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — {ORG_NAME}")
        if os.path.exists(resource("assets", "logo.png")):
            self.setWindowIcon(QIcon(resource("assets", "logo.png")))
        self.resize(1400, 860)
        self.pages: list[Page] = []
        self.current = -1
        self.thread = None

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._header())

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        root.addWidget(self.toolbar)
        self._actions()

        split = QSplitter()
        self.page_list = QListWidget()
        self.page_list.setViewMode(QListWidget.IconMode)
        self.page_list.setFlow(QListWidget.TopToBottom)
        self.page_list.setWrapping(False)
        self.page_list.setMovement(QListWidget.Static)
        self.page_list.setIconSize(QPixmap(160, 90).size())
        self.page_list.setSpacing(4)
        self.page_list.setFixedWidth(196)
        self.page_list.currentRowChanged.connect(self.go_to)
        split.addWidget(self.page_list)
        self.canvas = Canvas()
        self.canvas.scene().selectionChanged.connect(self.on_selection)
        split.addWidget(self.canvas)
        split.addWidget(self._panel())
        split.setStretchFactor(1, 1)
        root.addWidget(split, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("請按「開啟檔案」，選擇 PPTX、PDF 或圖片（JPG／PNG）。")
        self.on_selection()

    def _header(self):
        w = QWidget()
        w.setStyleSheet("background:#0b3a5b;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(12, 8, 12, 8)
        logo = QLabel()
        path = resource("assets", "logo.png")
        if os.path.exists(path):
            logo.setPixmap(QPixmap(path).scaledToHeight(52, Qt.SmoothTransformation))
        else:
            logo.setText(ORG_NAME)
            logo.setStyleSheet("color:white;border:1px solid white;padding:10px;font-size:15px;")
        lay.addWidget(logo)
        title = QLabel(f"<span style='font-size:20px;font-weight:600;color:white'>{APP_NAME}</span>"
                       f"<br><span style='color:#b9d4e8'>{ORG_NAME}</span>")
        lay.addWidget(title)
        lay.addStretch(1)
        return w

    def _actions(self):
        def act(text, slot, shortcut=None):
            a = QAction(text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(shortcut)
            self.toolbar.addAction(a)
            return a

        act("開啟檔案", self.open_files, QKeySequence.Open)
        self.export_action = act("匯出 PPTX", self.export, QKeySequence.Save)
        self.toolbar.addSeparator()
        act("新增文字方塊", self.add_block)
        act("刪除文字方塊", self.delete_selected, QKeySequence.Delete)
        self.toolbar.addSeparator()
        self.chk_original = QCheckBox("顯示原圖")
        self.chk_original.toggled.connect(self.canvas_show_original)
        self.toolbar.addWidget(self.chk_original)
        self.toolbar.addSeparator()
        self.chk_watermark = QCheckBox("移除浮水印")
        self.chk_watermark.setChecked(True)
        self.toolbar.addWidget(self.chk_watermark)
        self.chk_trad = QCheckBox("簡體轉繁體")
        self.chk_trad.setChecked(True)
        self.toolbar.addWidget(self.chk_trad)

    def _panel(self):
        box = QGroupBox("文字格式")
        form = QFormLayout(box)
        self.font_box = QFontComboBox()
        self.font_box.setCurrentFont(QFont(DEFAULT_FONT))
        self.font_box.currentFontChanged.connect(lambda f: self.apply(family=f.family()))
        form.addRow("字型", self.font_box)
        self.size_box = QDoubleSpinBox()
        self.size_box.setRange(4, 200)
        self.size_box.setDecimals(1)
        self.size_box.setSuffix(" pt")
        self.size_box.valueChanged.connect(lambda v: self.apply(size_pt=v))
        form.addRow("字級", self.size_box)
        self.bold_box = QCheckBox("粗體")
        self.bold_box.toggled.connect(lambda on: self.apply(bold=on))
        form.addRow("", self.bold_box)
        self.color_btn = QPushButton("文字顏色…")
        self.color_btn.clicked.connect(self.pick_color)
        form.addRow("", self.color_btn)
        self.all_font_btn = QPushButton("此字型套用到全部頁面")
        self.all_font_btn.clicked.connect(self.font_to_all)
        form.addRow(self.all_font_btn)
        tip = QLabel("・單擊選取文字方塊，可拖曳移動\n・雙擊進入編輯，可修改文字\n"
                     "・編輯時先反白文字，再按「文字顏色」只改那幾個字\n・Delete 刪除選取的方塊")
        tip.setStyleSheet("color:#666")
        tip.setWordWrap(True)
        form.addRow(tip)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(box)
        lay.addStretch(1)
        w.setFixedWidth(280)
        return w

    # ----- pages -----

    def open_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "選擇檔案", "", "支援的檔案 (*.pptx *.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff);;所有檔案 (*)")
        if not paths:
            return
        if self.pages and QMessageBox.question(self, APP_NAME, "要取代目前已開啟的頁面嗎？\n選「否」會加在後面。") == QMessageBox.Yes:
            self.canvas.show_page(None)
            self.pages.clear()
            self.page_list.clear()
            self.current = -1
        self.run_worker(paths)

    def run_worker(self, paths):
        self.progress = QProgressDialog("載入辨識模型…", "取消", 0, 0, self)
        self.progress.setWindowTitle("文字辨識中")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.setMinimumDuration(0)
        self.thread = QThread()
        self.worker = Worker(paths, self.chk_watermark.isChecked(), self.chk_trad.isChecked(),
                             self.font_box.currentFont().family())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.page_ready.connect(self.add_page)
        self.worker.failed.connect(lambda msg: QMessageBox.warning(self, APP_NAME, f"處理失敗：{msg}"))
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.progress.close)
        self.progress.canceled.connect(lambda: setattr(self.worker, "cancelled", True))
        self.thread.start()

    def on_progress(self, done, total, label):
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        if label:
            self.progress.setLabelText(f"辨識中：{label}（{done + 1}/{total}）")

    def add_page(self, page: Page):
        self.pages.append(page)
        thumb = to_pixmap(cv2.resize(page.original, (160, int(160 * page.height / page.width))))
        self.page_list.addItem(QListWidgetItem(QIcon(thumb), str(len(self.pages))))
        if self.current < 0:
            self.page_list.setCurrentRow(0)

    def go_to(self, row):
        self.canvas.sync()
        self.current = row
        self.canvas.show_page(self.pages[row] if 0 <= row < len(self.pages) else None)
        self.canvas.set_show_original(self.chk_original.isChecked())
        self.on_selection()

    def canvas_show_original(self, on):
        self.canvas.set_show_original(on)

    # ----- editing -----

    def add_block(self):
        page = self.canvas.page
        if page is None:
            return
        px = pt_to_px(page, 18)
        b = Block(page.width * 0.1, page.height * 0.1, page.width * 0.3, px * 1.4,
                  [[Run("新文字", (0, 0, 0))]], px, False, self.font_box.currentFont().family())
        page.blocks.append(b)
        item = TextItem(page, b)
        self.canvas.scene().addItem(item)
        self.canvas.scene().clearSelection()
        item.setSelected(True)

    def delete_selected(self):
        focus = self.canvas.scene().focusItem()
        if isinstance(focus, TextItem) and focus.textInteractionFlags() & Qt.TextEditorInteraction:
            # while typing, Delete belongs to the text editor
            cur = focus.textCursor()
            cur.deleteChar()
            focus.setTextCursor(cur)
            return
        for it in self.canvas.selected_items():
            self.canvas.scene().removeItem(it)

    def on_selection(self):
        items = self.canvas.selected_items()
        for w in (self.font_box, self.size_box, self.bold_box, self.color_btn):
            w.setEnabled(bool(items))
        if not items:
            return
        f = items[0].font()
        for w in (self.font_box, self.size_box, self.bold_box):
            w.blockSignals(True)
        self.font_box.setCurrentFont(QFont(f.family()))
        self.size_box.setValue(px_to_pt(items[0].page, f.pixelSize()))
        self.bold_box.setChecked(f.bold())
        for w in (self.font_box, self.size_box, self.bold_box):
            w.blockSignals(False)

    def apply(self, family=None, size_pt=None, bold=None):
        for it in self.canvas.selected_items():
            f = it.font()
            if family is not None:
                f.setFamily(family)
            if size_pt is not None:
                f.setPixelSize(max(1, round(pt_to_px(it.page, size_pt))))
            if bold is not None:
                f.setBold(bold)
            it.setFont(f)

    def pick_color(self):
        focus = self.canvas.scene().focusItem()
        editing = isinstance(focus, TextItem) and focus.textCursor().hasSelection()
        color = QColorDialog.getColor(parent=self, title="文字顏色")
        if not color.isValid():
            return
        fmt = QTextCharFormat()
        fmt.setForeground(QBrush(color))
        targets = [focus] if editing else self.canvas.selected_items()
        for it in targets:
            cur = it.textCursor() if editing else QTextCursor(it.document())
            if not editing:
                cur.select(QTextCursor.Document)
            cur.mergeCharFormat(fmt)

    def font_to_all(self):
        family = self.font_box.currentFont().family()
        self.canvas.sync()
        for p in self.pages:
            for b in p.blocks:
                b.font = family
        self.canvas.show_page(self.canvas.page)
        self.statusBar().showMessage(f"全部頁面已改用「{family}」", 5000)

    # ----- export -----

    def export(self):
        if not self.pages:
            QMessageBox.information(self, APP_NAME, "請先開啟檔案。")
            return
        self.canvas.sync()
        path, _ = QFileDialog.getSaveFileName(self, "匯出 PPTX", "分離結果.pptx", "PowerPoint (*.pptx)")
        if not path:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            export_pptx(self.pages, path)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"匯出失敗：{e}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f"已匯出：{path}", 8000)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont(DEFAULT_FONT, 10))
    win = MainWindow()
    win.show()
    for p in sys.argv[1:]:  # files dropped on the exe / passed on the command line
        if os.path.exists(p):
            win.run_worker(sys.argv[1:])
            break
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
