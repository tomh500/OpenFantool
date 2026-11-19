from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
from pages.audio_status_badge import create_badge_label, render_badges
from page_theme_helper import init_themed_page, style_as_card, style_as_primary_button, style_as_secondary_button
from service_urls import ACCOUNT_REGISTER_URL, OFFICIAL_WEBSITE_URL
from widgets.page_header import PageHeader
from widgets.page_action_bar import PageActionBar
from widgets.page_route import page_route, wire_page_routes

def _logged_out_hint() -> str:
    '''未登录时那句话。**全仓只此一份**（原先构造期与 `show_logged_out()` 各写一遍）。

⛔⛔ RN-475：三个页名**传字面量、不走 `page_label()`** —— 两处调用都在构造期，
那时页面还没挂进窗口，动态取名会退成「设置」（RN-584）。代价是会和导航漂开
⇒ 判据钉住它们逐字在名表里。叙事见档案。
'''
    return ('还没登录。' + page_route('crosshair', '「准心设置」') + '、'
            + page_route('kill_sound', '「击杀音效」') + '、'
            + page_route('magnifier', '「开镜放大」') + '这些功能本来就不需要账号，不想登录直接用就行。')


















class AccountPage(QWidget):
    login_requested = Signal(str, str, bool)
    refresh_requested = Signal()
    logout_requested = Signal()

    def __init__(self):
        super().__init__()
        self._mode = 'logged_out'
        self._busy = False
        self._online = False
        self._build_ui()
        self.show_logged_out()
        init_themed_page(self)


    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root_layout.addWidget(scroll, 1)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        page_header = PageHeader('账号中心', description = '桌面端和官网账号的连接口。目前只用来显示登录状态，云端同步等能力还没上线。', title_font_size = None, spacing = 4)
        self.message_label = page_header.description_label
        header_row.addWidget(page_header, 1)
        layout.addLayout(header_row)
        from ui_help_panel import PAGE_HELP_TEXTS, install_help_panel
        install_help_panel(header_row, layout, PAGE_HELP_TEXTS['account'])
        self.status_card = QFrame()
        style_as_card(self.status_card)
        status_layout = QVBoxLayout(self.status_card)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(8)
        status_header_row = QHBoxLayout()
        status_header_row.setSpacing(10)
        status_title = QLabel('当前状态')
        status_title.setObjectName('statusLabel')
        status_header_row.addWidget(status_title)
        self.status_badge_label = create_badge_label()
        status_header_row.addWidget(self.status_badge_label, 1)
        status_header_row.addStretch()
        status_layout.addLayout(status_header_row)
        self.stage_hint_label = QLabel(_logged_out_hint())
        self.stage_hint_label.setWordWrap(True)
        self.stage_hint_label.setObjectName('hintLabel')
        wire_page_routes(self.stage_hint_label)
        status_layout.addWidget(self.stage_hint_label)
        layout.addWidget(self.status_card)
        self.login_card = QFrame()
        style_as_card(self.login_card)
        login_layout = QVBoxLayout(self.login_card)
        login_layout.setContentsMargins(14, 12, 14, 12)
        login_layout.setSpacing(8)
        login_title = QLabel('登录账号')
        login_title.setObjectName('sectionTitle')
        login_layout.addWidget(login_title)
        self.login_hint_label = QLabel(f'''用 {OFFICIAL_WEBSITE_URL} 的账号登录。⚠ 这不是 Steam 账号，别填 Steam 的邮箱和密码。''')
        self.login_hint_label.setWordWrap(True)
        self.login_hint_label.setObjectName('hintLabel')
        login_layout.addWidget(self.login_hint_label)
        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(12)
        form_grid.setVerticalSpacing(6)
        email_label = QLabel('邮箱')
        self.email_input = QLineEdit()
        self.email_input.setMinimumHeight(36)
        self.email_input.setPlaceholderText('请输入官网账号邮箱')
        form_grid.addWidget(email_label, 0, 0)
        form_grid.addWidget(self.email_input, 0, 1)
        password_label = QLabel('密码')
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('请输入密码')
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(36)
        self.password_input.returnPressed.connect(self._emit_login)
        form_grid.addWidget(password_label, 1, 0)
        form_grid.addWidget(self.password_input, 1, 1)
        login_layout.addLayout(form_grid)
        self.remember_checkbox = QCheckBox('记住登录状态')
        self.remember_checkbox.setChecked(True)
        login_layout.addWidget(self.remember_checkbox)
        login_button_row = QHBoxLayout()
        login_button_row.setSpacing(10)
        self.login_button = QPushButton('登录账号')
        style_as_primary_button(self.login_button)
        self.login_button.setMinimumWidth(136)
        self.login_button.setFixedHeight(38)
        self.login_button.clicked.connect(self._emit_login)
        login_button_row.addWidget(self.login_button)
        self.register_button = QPushButton('注册账号')
        style_as_secondary_button(self.register_button)
        self.register_button.setMinimumWidth(118)
        self.register_button.setFixedHeight(38)
        self.register_button.setToolTip(f'''在浏览器里打开 {ACCOUNT_REGISTER_URL}''')
        self.register_button.clicked.connect(self._open_register)
        login_button_row.addWidget(self.register_button)
        login_button_row.addStretch()
        login_layout.addLayout(login_button_row)
        self.signup_hint_label = QLabel(f'''还没有账号？点「{self.register_button.text()}」会在浏览器里打开官网的注册页。''')
        self.signup_hint_label.setObjectName('hintLabel')
        self.signup_hint_label.setWordWrap(True)
        login_layout.addWidget(self.signup_hint_label)
        layout.addWidget(self.login_card)
        self.benefits_card = QFrame()
        style_as_card(self.benefits_card)
        benefits_layout = QVBoxLayout(self.benefits_card)
        benefits_layout.setContentsMargins(14, 12, 14, 14)
        benefits_layout.setSpacing(10)
        benefits_title = QLabel('登录能得到什么')
        benefits_title.setObjectName('sectionTitle')
        benefits_layout.addWidget(benefits_title)
        benefits_caption = QLabel('现在没有非登录不可的理由，想好了再登录也不迟。')
        benefits_caption.setObjectName('hintLabel')
        benefits_caption.setWordWrap(True)
        benefits_layout.addWidget(benefits_caption)
        benefits_grid = QGridLayout()
        benefits_grid.setHorizontalSpacing(14)
        benefits_grid.setVerticalSpacing(10)
        benefits_grid.setColumnStretch(0, 1)
        benefits_grid.setColumnStretch(1, 1)
        benefit_items = [
            ('●', '现在：只有一件', '桌面端会显示你的官网登录状态，会话快到期时自动续期。别的都不变。'),
            ('○', '以后：还没上线', '云端配置同步、多设备保留设置、付费 / 激活 —— 都还没做好。先登录的好处只是到时候不用重新登录一遍。')]
        for idx, (icon_text, head, desc) in enumerate(benefit_items):
            item = self._create_benefit_item(icon_text, head, desc)
            benefits_grid.addWidget(item, 0, idx)
        benefits_layout.addLayout(benefits_grid)
        layout.addWidget(self.benefits_card)
        self.info_card = QFrame()
        style_as_card(self.info_card)
        info_layout = QVBoxLayout(self.info_card)
        info_layout.setContentsMargins(14, 14, 14, 14)
        info_layout.setSpacing(10)
        info_header_row = QHBoxLayout()
        info_title_column = QVBoxLayout()
        info_title_column.setSpacing(4)
        info_title = QLabel('当前账号')
        info_title.setObjectName('sectionTitle')
        info_title_column.addWidget(info_title)
        self.profile_name_label = QLabel('未连接账号')
        self.profile_name_label.setObjectName('sectionTitle')
        self.profile_name_label.setWordWrap(True)
        self.profile_name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        info_title_column.addWidget(self.profile_name_label)
        self.profile_caption_label = QLabel(f'''当前桌面端还没有连接到 {OFFICIAL_WEBSITE_URL} 账号。''')
        self.profile_caption_label.setWordWrap(True)
        self.profile_caption_label.setObjectName('hintLabel')
        info_title_column.addWidget(self.profile_caption_label)
        info_header_row.addLayout(info_title_column, 1)
        info_layout.addLayout(info_header_row)
        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(14)
        info_grid.setVerticalSpacing(10)
        info_grid.setColumnStretch(0, 1)
        info_grid.setColumnStretch(1, 1)
        self.username_value = QLabel('-')
        self.email_value = QLabel('-')
        self.account_type_value = QLabel('-')
        self.expiry_value = QLabel('-')
        self.connection_value = QLabel('未连接')
        field_blocks = [
            ('用户名', self.username_value, 0, 0),
            ('邮箱', self.email_value, 0, 1),
            ('账号类型', self.account_type_value, 1, 0),
            ('会话有效期', self.expiry_value, 1, 1)]
        for label_text, value_label, row, column in field_blocks:
            info_grid.addWidget(self._create_info_field(label_text, value_label), row, column)
        info_layout.addLayout(info_grid)
        account_button_row = QHBoxLayout()
        account_button_row.setSpacing(10)
        account_action_hint = QLabel('')
        account_action_hint.setObjectName('hintLabel')
        account_action_hint.setWordWrap(True)
        account_button_row.addWidget(account_action_hint, 1)
        self.account_action_hint_label = account_action_hint
        self.account_action_hint_label.setText('登录状态会自动保持：会话临近过期时软件会尝试自动续期。刷新状态与退出登录在页面底部操作栏。')
        account_button_row.addStretch()
        self.info_website_button = QPushButton('打开官网')
        style_as_secondary_button(self.info_website_button)
        self.info_website_button.setMinimumWidth(110)
        self.info_website_button.setFixedHeight(38)
        self.info_website_button.clicked.connect(self._open_website)
        account_button_row.addWidget(self.info_website_button)
        info_layout.addLayout(account_button_row)
        layout.addWidget(self.info_card)
        layout.addStretch()
        self.action_bar = PageActionBar(self)
        self.action_bar.secondary_btn.setMinimumWidth(116)
        self.action_bar.primary_btn.setMinimumWidth(116)
        root_layout.addWidget(self.action_bar, 0)
        self.remember_checkbox.toggled.connect((lambda _checked: self._refresh_status_strip()))


    def _open_website(self):
        QDesktopServices.openUrl(QUrl(OFFICIAL_WEBSITE_URL))


    def _open_register(self):
        QDesktopServices.openUrl(QUrl(ACCOUNT_REGISTER_URL))


    def _create_info_field(self, title, value_label):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(title)
        label.setObjectName('hintLabel')
        layout.addWidget(label)
        value_label.setWordWrap(True)
        value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(value_label)
        return container


    def _emit_login(self):
        self.login_requested.emit(self.email_input.text().strip(), self.password_input.text(), bool(self.remember_checkbox.isChecked()))


    def _compact_text(self, value, fallback="未设置", max_length=14):
        text = str(value or "").strip()
        if text in {"", "-", "--"}:
            text = fallback
        if len(text) > max_length:
            return text[:max_length - 1] + "…"
        return text


    def _refresh_status_strip(self):
        remember_enabled = bool(self.remember_checkbox.isChecked())
        if self._mode == "logged_in":
            if self._busy:
                account_badge = ("info", "账号 · 刷新中")
            else:
                account_badge = ("positive", "账号 · 在线") if self._online else ("warning", "账号 · 离线会话")
            badges = [
                account_badge,
                ("info", f"类型 · {self._compact_text(self.account_type_value.text(), '待识别', 12)}"),
                ("info", f"有效期 · {self._compact_text(self.expiry_value.text(), '未知', 16)}"),
            ]
            detail_text = (
                f"当前账号：{self.username_value.text() or '-'}"
                f"\n邮箱：{self.email_value.text() or '-'}"
                f"\n账号类型：{self.account_type_value.text() or '-'}"
                f"\n连接状态：{self.connection_value.text() or '-'}"
                f"\n会话有效期：{self.expiry_value.text() or '-'}"
                f"\n状态提示：{self.message_label.text()}"
            )
        else:
            if self._busy:
                account_badge = ("info", "账号 · 连接中")
            else:
                account_badge = ("warning", "账号 · 未登录")
            badges = [
                account_badge,
                ("positive" if remember_enabled else "info", f"记住 · {'已开启' if remember_enabled else '未开启'}"),
            ]
            detail_text = (
                f"当前未连接 {OFFICIAL_WEBSITE_URL} 账号。\n记住登录：{'已开启' if remember_enabled else '未开启'}"
                f"\n状态提示：{self.message_label.text()}\n不登录不影响任何现有功能。"
            )
        render_badges(self.status_badge_label, badges, detail_tooltip=detail_text)
        self.status_card.setToolTip(detail_text)
        self._sync_action_bar()


    def _sync_action_bar(self):
        if not hasattr(self, "action_bar"):
            return
        if self._mode == "logged_in":
            self.action_bar.configure_secondary("刷新状态", self.refresh_requested.emit, visible=True)
            self.action_bar.configure_primary("退出登录", self.logout_requested.emit, visible=True)
            action_message = (
                f"当前账号：{self.username_value.text() or '-'} · "
                f"{'在线' if self._online else '离线缓存'} · "
                f"{self._compact_text(self.account_type_value.text(), '待识别', 14)}"
            )
            self.action_bar.secondary_btn.setEnabled(not self._busy)
            self.action_bar.primary_btn.setEnabled(not self._busy)
        else:
            self.action_bar.configure_secondary("", None, visible=False)
            self.action_bar.configure_primary("", None, visible=False)
            action_message = (
                f"当前未登录 · 记住状态{'已开启' if self.remember_checkbox.isChecked() else '未开启'}"
                f" · {'连接中，请稍候' if self._busy else '登录是可选的'}"
            )
        self.action_bar.set_message(action_message)


    def _apply_mode_visibility(self):
        is_logged_in = self._mode == 'logged_in'
        self.login_card.setVisible(not is_logged_in)
        self.info_card.setVisible(is_logged_in)
        if hasattr(self, 'benefits_card'):
            self.benefits_card.setVisible(not is_logged_in)


    def _create_benefit_item(self, icon_text: str, head: str, desc: str) -> QWidget:
        '''单个权益项：左侧圆点 + 标题 + 描述。'''
        wrap = QWidget()
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        dot = QLabel(icon_text)
        dot.setObjectName('hintLabel')
        dot.setFixedWidth(14)
        dot.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        from ui_style_applier import keep_inline_style
        keep_inline_style(dot)
        dot.setStyleSheet('color: #6366f1; font-size: 14px; font-weight: bold;')
        h.addWidget(dot, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel(head)
        title.setObjectName('statusLabel')
        col.addWidget(title)
        body = QLabel(desc)
        body.setObjectName('hintLabel')
        body.setWordWrap(True)
        col.addWidget(body)
        h.addLayout(col, 1)
        return wrap


    def _apply_controls(self):
        if self._busy:
            login_enabled = False
            refresh_enabled = False
            logout_enabled = False
        elif self._mode == 'logged_in':
            login_enabled = False
            refresh_enabled = True
            logout_enabled = True
        else:
            login_enabled = True
            refresh_enabled = False
            logout_enabled = False
        self.email_input.setEnabled(login_enabled)
        self.password_input.setEnabled(login_enabled)
        self.remember_checkbox.setEnabled(login_enabled)
        self.login_button.setEnabled(login_enabled)
        if hasattr(self, 'action_bar'):
            self.action_bar.secondary_btn.setEnabled(refresh_enabled if logout_enabled else not (self._busy))
            self.action_bar.primary_btn.setEnabled(logout_enabled or not self._busy)
        self.register_button.setEnabled(not (self._busy))
        self.info_website_button.setEnabled(not (self._busy))
        self._apply_mode_visibility()


    def show_logged_out(self, message=None):
        self._mode = 'logged_out'
        self._busy = False
        self._online = False
        self.message_label.setText(message or '桌面端和官网账号的连接口。目前只用来显示登录状态，云端同步等能力还没上线。')
        self.login_hint_label.setText(f'''用 {OFFICIAL_WEBSITE_URL} 的账号登录。⚠ 这不是 Steam 账号，别填 Steam 的邮箱和密码。''')
        self.stage_hint_label.setText(_logged_out_hint())
        self.profile_name_label.setText('未连接账号')
        self.profile_caption_label.setText('登录成功后，这里会展示当前连接到桌面端的官网账号信息。')
        self.username_value.setText('-')
        self.email_value.setText('-')
        self.account_type_value.setText('-')
        self.expiry_value.setText('-')
        self.connection_value.setText('未连接')
        self.password_input.clear()
        self._apply_controls()
        self._refresh_status_strip()


    def show_logged_in(self, profile, message=None, online=True):
        self._mode = 'logged_in'
        self._busy = False
        self._online = bool(online)
        username = profile.get('username') or '已连接账号'
        email = profile.get('email') or '-'
        account_type = profile.get('account_type') or '普通账号'
        expires_text = profile.get('expires_text') or '-'
        connection_text = '在线' if online else '离线缓存'
        self.message_label.setText(message or '已登录官网账号。云端同步等能力还没上线，登录状态本身不改变任何现有功能。')
        self.stage_hint_label.setText('已登录，会话快到期时软件会自动续期。账号信息在下面那张卡里。' if online else '已登录，但暂时连不上服务器，现在显示的是本地缓存的账号信息。')
        self.profile_name_label.setText(username)
        self.profile_caption_label.setText('桌面端已识别当前官网登录状态。后续如果接入配置同步和云端数据，这里会继续作为统一入口。')
        self.username_value.setText(username)
        self.email_value.setText(email)
        self.account_type_value.setText(account_type)
        self.expiry_value.setText(expires_text)
        self.connection_value.setText(connection_text)
        self.password_input.clear()
        if profile.get('email'):
            self.email_input.setText(profile.get('email'))
        self._apply_controls()
        self._refresh_status_strip()


    def set_busy(self, busy, message=None):
        self._busy = bool(busy)
        if message is not None:
            self.message_label.setText(message)
        self._apply_controls()
        self._refresh_status_strip()
