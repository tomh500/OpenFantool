from __future__ import annotations
import html
import re
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout
from core.net.offline import configure_text_links
from service_urls import SUPPORT_APP_SEARCH_KEYWORD, SUPPORT_APP_SEARCH_URL, SUPPORT_BILIBILI_NAME, SUPPORT_BILIBILI_SEARCH_URL, SUPPORT_GROUP_ID
DRAWN_OVER_THE_GAME = False
_URL_PATTERN = re.compile('https?://[^\\s<>\\"]+')

def _normalize_service_error_text(error):
    text = str(error or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) > 220:
        return text[:217] + "..."
    return text


def build_update_service_unavailable_text(error):
    detail = _normalize_service_error_text(error)
    lines = [
        '当前暂时无法连接更新服务器。',
        '',
        '如果你需要获取最新版，可以通过这些方式找到我们：',
        f'''- QQ群：{SUPPORT_GROUP_ID}''',
        f'''- B站搜索并关注：{SUPPORT_BILIBILI_NAME}''',
        f'''- 浏览器直接搜索：{SUPPORT_APP_SEARCH_KEYWORD}''',
        '',
        '你可以先关闭窗口继续使用当前版本，稍后再手动更新。']
    if detail:
        lines.extend(["", f"最近错误：{detail}"])
    return '\n'.join(lines).strip()


def build_account_service_unavailable_text(error):
    detail = _normalize_service_error_text(error)
    lines = [
        '当前暂时无法连接账号服务。',
        '',
        '你可以先继续使用本地功能，稍后再重新尝试登录。',
        '',
        '如果长时间无法恢复，可以通过这些方式找到我们：',
        f'''- QQ群：{SUPPORT_GROUP_ID}''',
        f'''- B站搜索并关注：{SUPPORT_BILIBILI_NAME}''',
        f'''- 浏览器直接搜索：{SUPPORT_APP_SEARCH_KEYWORD}''',
        '',
        '这些渠道会同步公告、更新动态和后续处理方式。']
    if detail:
        lines.extend(["", f"最近错误：{detail}"])
    return '\n'.join(lines).strip()


# Bytecode source-line anchor.























class ServiceUnavailableDialog(QDialog):
    def __init__(self, title_text, subtitle_text, body_text, parent=None):
        super().__init__(parent)
        self.setObjectName("updateInfoDialog")
        self._title_text = str(title_text or "服务连接失败").strip() or "服务连接失败"
        self._subtitle_text = str(subtitle_text or "").strip()
        self._body_text = str(body_text or "").strip()
        self.setWindowTitle(self._title_text)
        self.resize(800, 600)
        self.setMinimumSize(600, 400)
        self._create_ui()
        self._center_window()

    def _create_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        title_label = QLabel(self._title_text)
        title_label.setFont(QFont('Microsoft YaHei', 20, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        if self._subtitle_text:
            subtitle_label = QLabel(self._subtitle_text)
            subtitle_label.setWordWrap(True)
            subtitle_label.setAlignment(Qt.AlignCenter)
            subtitle_label.setFont(QFont('Microsoft YaHei UI', 11))
            main_layout.addWidget(subtitle_label)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)
        self.text_area = QTextBrowser()
        self.text_area.setObjectName('updateInfoBody')
        self.text_area.setReadOnly(True)
        configure_text_links(self.text_area)
        self.text_area.setHtml(self._build_rich_text_html(self._body_text))
        self.text_area.document().setDocumentMargin(16)
        self.text_area.setFont(QFont('Microsoft YaHei UI', 12))
        main_layout.addWidget(self.text_area)
        hint_label = QLabel('提示：这不会阻止当前软件继续使用，只是暂时无法自动连接对应服务。')
        hint_label.setWordWrap(True)
        hint_label.setFont(QFont('Microsoft YaHei UI', 10))
        main_layout.addWidget(hint_label)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.copy_group_button = QPushButton('复制群号')
        self.copy_group_button.setObjectName('updatePrimaryCta')
        self.copy_group_button.setCursor(Qt.PointingHandCursor)
        self.copy_group_button.setMinimumWidth(130)
        self.copy_group_button.setFixedHeight(44)
        self.copy_group_button.clicked.connect(self._copy_group_id)
        button_layout.addWidget(self.copy_group_button)
        self.open_bilibili_button = QPushButton('打开B站搜索')
        self.open_bilibili_button.setObjectName('updateGhostCta')
        self.open_bilibili_button.setCursor(Qt.PointingHandCursor)
        self.open_bilibili_button.setMinimumWidth(150)
        self.open_bilibili_button.setFixedHeight(44)
        self.open_bilibili_button.clicked.connect((lambda: QDesktopServices.openUrl(QUrl(SUPPORT_BILIBILI_SEARCH_URL))))
        button_layout.addWidget(self.open_bilibili_button)
        self.search_app_button = QPushButton(f'''搜索{SUPPORT_APP_SEARCH_KEYWORD}''')
        self.search_app_button.setObjectName('updateGhostCta')
        self.search_app_button.setCursor(Qt.PointingHandCursor)
        self.search_app_button.setMinimumWidth(150)
        self.search_app_button.setFixedHeight(44)
        self.search_app_button.clicked.connect((lambda: QDesktopServices.openUrl(QUrl(SUPPORT_APP_SEARCH_URL))))
        button_layout.addWidget(self.search_app_button)
        button_layout.addStretch()
        self.close_button = QPushButton('关闭继续使用')
        self.close_button.setObjectName('updateGhostCta')
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setMinimumWidth(140)
        self.close_button.setFixedHeight(44)
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)
        self._apply_dialog_button_style()


    def _apply_dialog_button_style(self):
        self.setStyleSheet("""
            QDialog#updateInfoDialog QPushButton#updatePrimaryCta {
                color: white;
                border: none;
                border-radius: 12px;
                padding: 0 18px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3a7bd5, stop:1 #4f8ff5);
            }
            QDialog#updateInfoDialog QPushButton#updatePrimaryCta:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4a89e0, stop:1 #63a2ff);
            }
            QDialog#updateInfoDialog QPushButton#updatePrimaryCta:pressed {
                background: #386fbe;
            }
            QDialog#updateInfoDialog QPushButton#updateGhostCta {
                color: #d8dee9;
                border: 1px solid #3a4556;
                border-radius: 12px;
                padding: 0 16px;
                background-color: rgba(255, 255, 255, 0.02);
            }
            QDialog#updateInfoDialog QPushButton#updateGhostCta:hover {
                border-color: #5a6b82;
                background-color: rgba(255, 255, 255, 0.06);
            }
            QDialog#updateInfoDialog QPushButton#updateGhostCta:pressed {
                background-color: rgba(255, 255, 255, 0.10);
            }
            QDialog#updateInfoDialog QTextBrowser#updateInfoBody {
                border: 1px solid #2f3b4d;
                border-radius: 12px;
                padding: 4px;
                background-color: rgba(255, 255, 255, 0.02);
                selection-background-color: #4f8ff5;
            }
            QDialog#updateInfoDialog QTextBrowser#updateInfoBody:focus {
                border-color: #4f8ff5;
            }
            """)

    def _build_rich_text_html(self, body_text):
        lines = [line.strip() for line in str(body_text or "").splitlines() if line.strip()]
        if not lines:
            lines = ["暂无可展示内容。"]

        body_html = "".join(self._line_to_paragraph_html(line) for line in lines)
        return (
            "<html><head><style>"
            "body{margin:0;font-family:'Microsoft YaHei UI';font-size:15px;line-height:1.72;}"
            "p{margin:0 0 10px 0;}"
            "p.heading{margin:8px 0 10px 0;font-size:17px;font-weight:700;}"
            "p.item{padding-left:2px;}"
            "a{text-decoration:underline;font-weight:600;}"
            "</style></head><body>"
            f"{body_html}"
            "</body></html>"
        )

    def _line_to_paragraph_html(self, line):
        text = line.strip()
        if not text:
            return ""

        if text.startswith(("- ", "• ", "* ", "· ")):
            text = text[2:].strip()
            return f"<p class='item'>• {self._linkify_plain_text(text)}</p>"

        if text.endswith(("：", ":")):
            return f"<p class='heading'>{self._linkify_plain_text(text)}</p>"

        if text.startswith(("【", "[", "更新", "公告", "版本", "当前")) and len(text) <= 18:
            return f"<p class='heading'>{self._linkify_plain_text(text)}</p>"

        return f"<p class='item'>{self._linkify_plain_text(text)}</p>"

    def _linkify_plain_text(self, text):
        result_parts = []
        last_index = 0
        for match in _URL_PATTERN.finditer(text):
            start, end = match.span()
            if start > last_index:
                result_parts.append(html.escape(text[last_index:start]))

            raw_url = match.group(0)
            trimmed_url = raw_url.rstrip(".,;!?)]")
            trailing = raw_url[len(trimmed_url):]
            if not trimmed_url:
                result_parts.append(html.escape(raw_url))
                last_index = end
                continue

            escaped_url = html.escape(trimmed_url, quote=True)
            result_parts.append(f"<a href='{escaped_url}'>{html.escape(trimmed_url)}</a>")
            if trailing:
                result_parts.append(html.escape(trailing))

            last_index = end

        if last_index < len(text):
            result_parts.append(html.escape(text[last_index:]))
        return "".join(result_parts)

    def _copy_group_id(self):
        QApplication.clipboard().setText(SUPPORT_GROUP_ID)
        self.copy_group_button.setText('群号已复制')


    def _center_window(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        screen_geometry = screen.geometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)


# Bytecode source-line anchor.
















class UpdateServiceUnavailableDialog(ServiceUnavailableDialog):
    def __init__(self, error_text, parent=None):
        super().__init__(
            "更新服务连接失败",
            "当前无法自动获取更新公告，请通过下方渠道手动查找最新版。",
            build_update_service_unavailable_text(error_text),
            parent=parent,
        )


class AccountServiceUnavailableDialog(ServiceUnavailableDialog):
    def __init__(self, error_text, parent=None):
        super().__init__(
            "账号服务连接失败",
            "当前无法连接官网登录服务，你可以先继续使用本地功能，稍后再尝试登录。",
            build_account_service_unavailable_text(error_text),
            parent=parent,
        )


def _dialog_is_alive(dialog):
    if dialog is None:
        return False
    try:
        dialog.windowTitle()
        return True
    except RuntimeError:
        return False


def _present_dialog(dialog):
    try:
        if dialog.isMinimized():
            dialog.showNormal()
    except RuntimeError:
        return
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def show_singleton_dialog(parent, attr_name, dialog_factory):
    existing = getattr(parent, attr_name, None) if parent is not None else None
    if _dialog_is_alive(existing):
        _present_dialog(existing)
        return existing

    dialog = dialog_factory()
    dialog.setModal(False)
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)

    if parent is not None:
        setattr(parent, attr_name, dialog)

        def _clear_dialog_reference(*_args):
            try:
                current = getattr(parent, attr_name, None)
            except RuntimeError:
                return
            if current is dialog:
                setattr(parent, attr_name, None)

        dialog.destroyed.connect(_clear_dialog_reference)

    _present_dialog(dialog)
    return dialog
