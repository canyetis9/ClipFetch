import sys
import subprocess
import os

def _check_and_install_dependencies():
    missing = []
    try:
        import yt_dlp
    except ImportError:
        missing.append('yt-dlp')
    try:
        import PySide6
    except ImportError:
        missing.append('PySide6>=6.6')
    if missing:
        print('[ClipFetch] Installing missing dependencies:', missing)
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade'] + missing)
        print('[ClipFetch] Setup complete!')

_check_and_install_dependencies()

import yt_dlp
from PySide6.QtCore import Qt, QThread, QTimer, QStandardPaths, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QButtonGroup, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

PRIMARY_COLOR = "#6366f1"
BACKGROUND_COLOR = "#09090b"
CARD_COLOR = "#18181b"
BORDER_COLOR = "#27272a"
TEXT_PRIMARY = "#fafafa"
TEXT_SECONDARY = "#a1a1aa"

STYLESHEET = f"""
* {{ font-family: 'Segoe UI', 'Inter', 'Helvetica Neue', sans-serif; color: {TEXT_PRIMARY}; font-size: 14px; }}
QWidget#root {{ background: {BACKGROUND_COLOR}; }}
QFrame#card {{ background: {CARD_COLOR}; border: 1px solid {BORDER_COLOR}; border-radius: 12px; }}
QFrame#item {{ background: #131316; border: 1px solid {BORDER_COLOR}; border-radius: 10px; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 28px; font-weight: 800; letter-spacing: 1px; }}
QLabel#subtitle {{ color: {TEXT_SECONDARY}; font-size: 14px; }}
QLabel#cardTitle {{ font-size: 15px; font-weight: 700; }}
QLabel#dimmed {{ color: {TEXT_SECONDARY}; font-size: 13px; }}
QLabel#number {{ font-size: 26px; font-weight: 800; }}
QLabel#badge {{ font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 6px; 
                background: #1e1b4b; color: {PRIMARY_COLOR}; border: 1px solid #3730a3; }}
QLineEdit {{ background: #09090b; border: 1px solid {BORDER_COLOR}; border-radius: 8px;
            padding: 12px 14px; selection-background-color: {PRIMARY_COLOR}; }}
QLineEdit:focus {{ border: 1px solid {PRIMARY_COLOR}; }}
QPushButton {{ background: #27272a; border: 1px solid {BORDER_COLOR}; border-radius: 8px; padding: 10px 16px; font-weight: 600; }}
QPushButton:hover {{ background: #3f3f46; border: 1px solid #52525b; }}
QPushButton#primary {{ background: {PRIMARY_COLOR}; border: none; color: white; font-weight: 700; }}
QPushButton#primary:hover {{ background: #4f46e5; }}
QPushButton#primary:disabled {{ background: #312e81; color: #6b7280; }}
QPushButton#selectable {{ background: transparent; border: 1px solid {BORDER_COLOR}; }}
QPushButton#selectable:checked {{ background: #1e1b4b; border: 1px solid {PRIMARY_COLOR}; color: #818cf8; }}
QProgressBar {{ background: #27272a; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PRIMARY_COLOR}, stop:1 #818cf8); border-radius: 4px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #3f3f46; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""

class ToggleSwitch(QAbstractButton):
    def __init__(self):
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(54, 28)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(PRIMARY_COLOR) if self.isChecked() else QColor(BORDER_COLOR))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.right() - d - 3 if self.isChecked() else r.left() + 3
        p.setBrush(QColor("white"))
        p.drawEllipse(x, r.top() + 3, d, d)

class DownloadWorker(QThread):
    progress_signal = Signal(int, str)
    title_signal = Signal(str)
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, url, format_type, output_folder):
        super().__init__()
        self.url = url
        self.format_type = format_type
        self.output_folder = output_folder

    def _hook(self, d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                percent = int(d.get("downloaded_bytes", 0) * 100 / total)
                speed = (d.get("_speed_str") or "").strip()
                self.progress_signal.emit(min(percent, 99), f"Downloading · {percent}%  {speed}")
            info = d.get("info_dict") or {}
            if info.get("title"):
                self.title_signal.emit(info["title"])
        elif d.get("status") == "finished":
            self.progress_signal.emit(99, "Processing…")

    def run(self):
        options = {
            "outtmpl": os.path.join(self.output_folder, "%(title)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._hook],
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        }
        if self.format_type == "mp4":
            options["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        else:
            options["format"] = "bestaudio/best"
            options["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([self.url])
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

class DownloadItem(QFrame):
    def __init__(self, url, format_type):
        super().__init__()
        self.setObjectName("item")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        top_layout = QHBoxLayout()
        self.title_label = QLabel(url if len(url) < 60 else url[:57] + "…")
        self.title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        badge = QLabel(format_type.upper())
        badge.setObjectName("badge")
        badge.setFixedHeight(24)
        badge.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(self.title_label, 1)
        top_layout.addWidget(badge)
        main_layout.addLayout(top_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Waiting in queue…")
        self.status_label.setObjectName("dimmed")
        main_layout.addWidget(self.status_label)

    def update_progress(self, percent, text):
        self.progress_bar.setValue(percent)
        self.status_label.setText(text)

    def set_title(self, title):
        self.title_label.setText(title if len(title) < 60 else title[:57] + "…")

    def mark_completed(self):
        self.progress_bar.setValue(100)
        self.status_label.setText("Download Completed")
        self.status_label.setStyleSheet("color: #10b981;")

    def mark_failed(self):
        self.status_label.setText("Failed. Invalid link or content might be private.")
        self.status_label.setStyleSheet("color: #ef4444;")
        self.progress_bar.setValue(0)

def create_card(title_text=None):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    if title_text:
        t = QLabel(title_text)
        t.setObjectName("cardTitle")
        layout.addWidget(t)
    return frame, layout

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle("ClipFetch")
        self.resize(960, 740)
        self.setMinimumSize(800, 660)

        self.last_copied = ""
        self.current_format = "mp4"
        self.output_folder = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation) or os.path.join(os.path.expanduser("~"), "Desktop")
        self.workers = []
        self.total_count = self.success_count = self.fail_count = 0

        self._setup_ui()

        self.clipboard_timer = QTimer(self)
        self.clipboard_timer.setInterval(1000)
        self.clipboard_timer.timeout.connect(self._check_clipboard)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 24)
        main_layout.setSpacing(20)

        title_label = QLabel(f'CLIP<span style="color:{PRIMARY_COLOR};">FETCH</span>')
        title_label.setObjectName("title")
        subtitle = QLabel("Copy any video link, and the download starts automatically.")
        subtitle.setObjectName("subtitle")
        main_layout.addWidget(title_label)
        main_layout.addWidget(subtitle)

        # New Download Card
        c1, l1 = create_card("Manual Download")
        row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste a media link here…")
        self.url_input.returnPressed.connect(self._start_manual_download)
        self.download_btn = QPushButton("Download")
        self.download_btn.setObjectName("primary")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setMinimumWidth(120)
        self.download_btn.clicked.connect(self._start_manual_download)
        row.addWidget(self.url_input, 1)
        row.addWidget(self.download_btn)
        l1.addLayout(row)
        main_layout.addWidget(c1)

        # Monitor + Format Options
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(20)

        c2, l2 = create_card("Clipboard Monitor")
        row2 = QHBoxLayout()
        self.monitor_status = QLabel("Disabled")
        self.monitor_status.setStyleSheet("font-weight: 700; font-size: 15px;")
        self.monitor_switch = ToggleSwitch()
        self.monitor_switch.toggled.connect(self._toggle_monitor)
        row2.addWidget(self.monitor_status, 1)
        row2.addWidget(self.monitor_switch)
        l2.addLayout(row2)
        desc = QLabel("Automatically grab and download links you copy.")
        desc.setObjectName("dimmed")
        desc.setWordWrap(True)
        l2.addWidget(desc)
        middle_layout.addWidget(c2, 1)

        c3, l3 = create_card("Output Format")
        row3 = QHBoxLayout()
        self.btn_mp4 = QPushButton("MP4 (Video)")
        self.btn_mp3 = QPushButton("MP3 (Audio)")
        group = QButtonGroup(self)
        group.setExclusive(True)
        for b, fmt in ((self.btn_mp4, "mp4"), (self.btn_mp3, "mp3")):
            b.setObjectName("selectable")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            group.addButton(b)
            b.clicked.connect(lambda _=False, f=fmt: self._change_format(f))
            row3.addWidget(b)
        self.btn_mp4.setChecked(True)
        l3.addLayout(row3)
        note = QLabel("Requires FFmpeg for MP3 conversion.")
        note.setObjectName("dimmed")
        l3.addWidget(note)
        middle_layout.addWidget(c3, 1)
        main_layout.addLayout(middle_layout)

        # Save Location & Stats
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(20)

        c4, l4 = create_card("Save Location")
        row4 = QHBoxLayout()
        self.folder_label = QLabel(self.output_folder)
        self.folder_label.setObjectName("dimmed")
        self.folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        change_btn = QPushButton("Change")
        change_btn.setCursor(Qt.PointingHandCursor)
        change_btn.clicked.connect(self._select_folder)
        row4.addWidget(self.folder_label, 1)
        row4.addWidget(change_btn)
        l4.addLayout(row4)
        bottom_row.addWidget(c4, 3)

        self.stat_total = self._create_stat("Total")
        self.stat_success = self._create_stat("Success", "#10b981")
        self.stat_fail = self._create_stat("Failed", "#ef4444")
        for s in (self.stat_total, self.stat_success, self.stat_fail):
            bottom_row.addWidget(s[0], 1)
        main_layout.addLayout(bottom_row)

        # List Area
        list_header = QLabel("Recent Downloads")
        list_header.setObjectName("cardTitle")
        list_header.setStyleSheet("margin-top: 10px;")
        main_layout.addWidget(list_header)

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 8, 0)
        self.list_layout.setSpacing(12)
        self.empty_label = QLabel("No downloads yet. Copy a link or paste it above to begin.")
        self.empty_label.setObjectName("dimmed")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.list_layout.addWidget(self.empty_label)
        self.list_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.list_container)
        main_layout.addWidget(scroll_area, 1)

        self.status_bar = QLabel("Ready.")
        self.status_bar.setObjectName("dimmed")
        main_layout.addWidget(self.status_bar)

    def _create_stat(self, name, color="#fafafa"):
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        number = QLabel("0")
        number.setObjectName("number")
        number.setAlignment(Qt.AlignCenter)
        number.setStyleSheet(f"color: {color};")
        label = QLabel(name)
        label.setObjectName("dimmed")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(number)
        layout.addWidget(label)
        return frame, number

    def _set_status(self, text):
        self.status_bar.setText(text)

    def _toggle_monitor(self, enabled):
        if enabled:
            self.last_copied = QApplication.clipboard().text().strip()
            self.clipboard_timer.start()
            self.monitor_status.setText("Enabled")
            self.monitor_status.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {PRIMARY_COLOR};")
            self._set_status("Clipboard monitor active. Waiting for links...")
        else:
            self.clipboard_timer.stop()
            self.monitor_status.setText("Disabled")
            self.monitor_status.setStyleSheet("font-weight: 700; font-size: 15px;")
            self._set_status("Clipboard monitor paused.")

    def _change_format(self, format_type):
        self.current_format = format_type
        self._set_status(f"Output format changed to: {'MP4 (Video)' if format_type == 'mp4' else 'MP3 (Audio)'}")

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.output_folder)
        if folder:
            self.output_folder = folder
            self.folder_label.setText(folder)

    def _check_clipboard(self):
        content = QApplication.clipboard().text().strip()
        if content and content != self.last_copied and content.startswith("http"):
            self.last_copied = content
            self._start_download(content)

    def _start_manual_download(self):
        url = self.url_input.text().strip()
        if not url.startswith("http"):
            self._set_status("Please enter a valid URL (must start with http).")
            return
        self.url_input.clear()
        self._start_download(url)

    @staticmethod
    def _clean_url(url):
        if "?" in url and "youtube.com" not in url and "youtu.be" not in url:
            return url.split("?")[0]
        return url

    def _start_download(self, url):
        url = self._clean_url(url)
        item = DownloadItem(url, self.current_format)
        self.empty_label.hide()
        self.list_layout.insertWidget(0, item)
        self.total_count += 1
        self.stat_total[1].setText(str(self.total_count))
        self._set_status(f"Started downloading: {url[:60]}")

        worker = DownloadWorker(url, self.current_format, self.output_folder)
        worker.progress_signal.connect(item.update_progress)
        worker.title_signal.connect(item.set_title)
        worker.finished_signal.connect(lambda: self._on_worker_finished(item, worker, True))
        worker.error_signal.connect(lambda _m: self._on_worker_finished(item, worker, False))
        self.workers.append(worker)
        worker.start()

    def _on_worker_finished(self, item, worker, success):
        if success:
            item.mark_completed()
            self.success_count += 1
            self.stat_success[1].setText(str(self.success_count))
            self._set_status("Download completed successfully.")
        else:
            item.mark_failed()
            self.fail_count += 1
            self.stat_fail[1].setText(str(self.fail_count))
            self._set_status("A download has failed.")
        if worker in self.workers:
            self.workers.remove(worker)

    def closeEvent(self, event):
        for worker in self.workers:
            worker.wait(200)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
