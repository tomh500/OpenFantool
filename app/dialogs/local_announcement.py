"""Display a local Markdown announcement without fetching document resources."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout

from core.runtime.source_options import get_source_options
from service_unavailable_dialog import show_singleton_dialog


class AnnouncementText(QTextBrowser):
    def loadResource(self, resource_type, name):
        # The notice only renders text, including when its Markdown contains image URLs.
        return None


class LocalAnnouncementDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        options = get_source_options()
        self.setWindowTitle(options.announcement_title)
        self.resize(720, 460)
        self.setMinimumSize(460, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        title = QLabel(options.announcement_title)
        title.setTextFormat(Qt.PlainText)
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.text_area = AnnouncementText(self)
        self.text_area.setReadOnly(True)
        self.text_area.setOpenLinks(False)
        self.text_area.setOpenExternalLinks(False)
        features = QTextDocument.MarkdownDialectGitHub | QTextDocument.MarkdownNoHTML
        self.text_area.document().setMarkdown(options.announcement_text, features)
        self.text_area.document().setDocumentMargin(12)
        if not options.block_remote_network:
            self.text_area.anchorClicked.connect(self._open_link)
        layout.addWidget(self.text_area, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("关闭")
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    @staticmethod
    def _open_link(url):
        if url.scheme().lower() in {"https", "http"}:
            QDesktopServices.openUrl(url)


def show_local_announcement(parent):
    return show_singleton_dialog(parent, "_local_announcement_dialog", lambda: LocalAnnouncementDialog(parent))
