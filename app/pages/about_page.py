'''
关于页面 - PySide6 Widgets版本
功能：软件信息、版本、作者、更新日志
'''
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea, QTextEdit, QDialog, QMessageBox
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QDesktopServices
import json
import requests
from core.runtime.source_options import OFFLINE_MESSAGE, get_source_options
from config import VERSION
from core.utils.logger import get_logger
from pages.audio_status_badge import create_badge_label, render_badges
from theme_manager import get_color, get_theme_manager
from page_theme_helper import style_as_secondary_button
from service_urls import CHANGELOG_API_URL, CLIENT_UPDATE_API_URL, HELP_KIT_URL, OFFICIAL_WEBSITE_URL, OPENSOURCE_REPO_URL, SUPPORT_GROUP_ID
from widgets.page_header import PageHeader
from widgets.page_action_bar import PageActionBar
from widgets.settings_card import SettingsCard
















class ChangelogFetcher(QThread):
    '更新日志获取线程'
    finished = Signal(str)
    error = Signal(str)
    CHANGELOG_API_URL = CHANGELOG_API_URL
    UPDATE_POLICY_API_URL = CLIENT_UPDATE_API_URL

    def __init__(self):
        super().__init__()
        self.logger = get_logger('ChangelogFetcher')

    @staticmethod
    def _normalize_lines(value):
        if isinstance(value, list):
            values = value
        elif isinstance(value, str):
            values = value.splitlines()
        else:
            return []
        result = []
        for item in values:
            text = str(item or "").strip()
            if not text:
                continue
            result.append(text)
        return result

    @staticmethod
    def _normalize_download_links(value):
        if not isinstance(value, list):
            return []
        links = []
        for item in value:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            url = str(item.get("url") or "").strip()
            if not label:
                continue
            if not url:
                continue
            links.append((label, url))
        return links

    def _request_json(self, url):
        response = requests.get(url, timeout = 10, headers = {
            'User-Agent': 'FanTool-AboutPage/2.x',
            'Accept': 'application/json' })
        response.raise_for_status()
        payload = json.loads(response.content.decode('utf-8-sig', errors = 'replace'))
        if not isinstance(payload, dict):
            raise ValueError('服务器返回格式无效')
        return payload


    def _format_history_text(self, payload):
        data = payload.get("data") if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            data = {}
        current_release = data.get("current_release") if isinstance(data.get("current_release"), dict) else {}
        release_history = data.get("release_history") if isinstance(data.get("release_history"), list) else []
        changelog_lines = self._normalize_lines(data.get("changelog"))
        announcement_lines = self._normalize_lines(data.get("announcement_lines"))
        download_links = self._normalize_download_links(data.get("download_links"))
        latest_version = str(data.get("latest_version") or current_release.get("version") or "").strip()
        min_supported = str(data.get("min_supported_version") or "").strip()
        mandatory = bool(data.get("mandatory"))
        lines = []
        lines.append("帆派助手开放版 更新日志")
        if latest_version:
            lines.append(f"最新版本: v{latest_version}")
        if min_supported:
            lines.append(f"最低支持版本: v{min_supported}")
        lines.append(f"更新策略: {'强制更新' if mandatory else '常规更新'}")
        if announcement_lines:
            lines.append("")
            lines.append("公告摘要:")
            lines.extend(announcement_lines[:12])
        if release_history:
            lines.append("")
            lines.append("历史更新:")
            for item in release_history[:30]:
                if not isinstance(item, dict):
                    continue
                version = str(item.get("version") or "").strip() or "-"
                release_date = str(item.get("release_date") or "").strip()
                published_at = str(item.get("published_at") or "").strip()
                header = f"v{version}"
                if release_date:
                    header += f" | {release_date}"
                elif published_at:
                    header += f" | {published_at}"
                lines.append("")
                lines.append(header)
                item_lines = self._normalize_lines(item.get("changelog_lines"))
                if not item_lines:
                    notes = str(item.get("notes") or "").strip()
                    item_lines = [notes] if notes else ["暂无详细更新项"]
                for item_line in item_lines[:40]:
                    if item_line.startswith(("-", "*", "•")):
                        lines.append(item_line)
                    else:
                        lines.append(f"- {item_line}")
        elif changelog_lines:
            lines.append("")
            lines.append("历史更新:")
            lines.extend(changelog_lines[:240])
        else:
            lines.append("")
            lines.append("历史更新:")
            lines.append("暂无更新内容")
        if download_links:
            lines.append("")
            lines.append("下载地址:")
            for label, url in download_links[:5]:
                lines.append(f"- {label}: {url}")
        return "\n".join(lines).strip()


    def _format_policy_text(self, payload):
        data = payload.get("data") if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            data = {}
        latest_version = str(data.get("latest_version") or "").strip()
        announcement_lines = self._normalize_lines(data.get("announcement_lines"))
        min_supported = str(data.get("min_supported_version") or "").strip()
        mandatory = bool(data.get("mandatory"))
        download_links = self._normalize_download_links(data.get("download_links"))
        website = OFFICIAL_WEBSITE_URL
        lines = ["帆派助手开放版 更新公告"]
        if latest_version:
            lines.append(f"最新版本: v{latest_version}")
        if min_supported:
            lines.append(f"最低支持版本: v{min_supported}")
        lines.append(f"更新策略: {'强制更新' if mandatory else '常规更新'}")
        if announcement_lines:
            lines.append("")
            lines.append("公告内容:")
            lines.extend(announcement_lines[:18])
        else:
            lines.append("")
            lines.append("公告内容:")
            lines.append("暂无公告内容")
        lines.append("")
        lines.append(f"官网地址: {website}")
        if download_links:
            lines.append("备用下载:")
            for label, url in download_links[:5]:
                lines.append(f"- {label}: {url}")
        return "\n".join(lines).strip()


    def run(self):
        '''获取更新日志（优先主站API，失败时降级到更新策略API）'''
        try:
            self.logger.info("正在获取更新日志: get_changelog.php")
            payload = self._request_json(self.CHANGELOG_API_URL)
            content = self._format_history_text(payload)
            self.logger.info("更新日志获取成功")
            self.finished.emit(content)
            return
        except Exception as primary_error:
            self.logger.warning(f"主日志接口获取失败，尝试降级: {primary_error}")

        try:
            self.logger.info("正在获取更新公告降级数据: client_update.php")
            payload = self._request_json(self.UPDATE_POLICY_API_URL)
            content = self._format_policy_text(payload)
            self.logger.info("更新公告获取成功（降级）")
            self.finished.emit(content)
        except Exception as fallback_error:
            self.logger.error(f"获取更新日志失败: {fallback_error}")
            self.error.emit(str(fallback_error))












class ChangelogDialog(QDialog):
    '更新日志对话框'

    def __init__(self, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle('更新日志')
        self.resize(700, 600)
        self.setModal(True)
        self._create_ui(content)


    def _create_ui(self, content):
        '''创建UI'''
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        header_layout = QHBoxLayout()
        title = QLabel('更新日志')
        title.setFont(QFont('Microsoft YaHei', 24, QFont.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()
        version_label = QLabel(f'''当前版本: v{VERSION}''')
        version_label.setFont(QFont('Microsoft YaHei', 14))
        header_layout.addWidget(version_label)
        layout.addLayout(header_layout)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        content_text = QTextEdit()
        content_text.setReadOnly(True)
        content_text.setPlainText(content)
        content_text.setFont(QFont('Microsoft YaHei UI', 12))
        layout.addWidget(content_text)
        close_btn = QPushButton('关闭')
        close_btn.setObjectName('primaryButton')
        close_btn.setFixedHeight(36)
        close_btn.setFont(QFont('Microsoft YaHei', 12))
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


ONBOARDING_BUTTON_TEXT = '三步上手引导'






















class AboutPage(QWidget):
    '关于页面'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger('AboutPage')
        self.changelog_fetcher = None
        self.current_loading_msg = None
        self._create_ui()
        get_theme_manager().register_theme_changed_callback(self._apply_theme_styles)
        self._manual_check_result.connect(self._on_manual_check_result)
        self._manual_checking = False
        self.logger.info('关于页面初始化完成')

    _manual_check_result = Signal(object, str)

    def _manual_check_update(self):
        if get_source_options().block_remote_network:
            from ui_toast import toast_info

            toast_info(OFFLINE_MESSAGE)
            return
        if self._manual_checking:
            return
        self._manual_checking = True
        self.check_update_button.setEnabled(False)
        self.check_update_button.setText("检查中…")

        def _worker():
            try:
                from update_runtime import UpdateRuntimeChecker

                result = UpdateRuntimeChecker(logger=self.logger).check(VERSION)
                self._manual_check_result.emit(result, "")
            except Exception as e:
                self._manual_check_result.emit(None, str(e)[:120])

        import threading

        threading.Thread(target=_worker, name="ManualUpdateCheck", daemon=True).start()


    def _on_manual_check_result(self, result, error_text):
        self._manual_checking = False
        self.check_update_button.setEnabled(True)
        self.check_update_button.setText("立即检查更新")
        from ui_toast import toast_info, toast_success, toast_warning

        if result is None:
            toast_warning(f"检查更新失败：{error_text or '网络不可用'}", 4200)
            return
        if getattr(result, "blocked", False):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, "版本不可用",
                f"当前版本 v{VERSION} 已停用\n{result.block_message or '请前往官网更新。'}",
            )
            return
        if getattr(result, "update_available", False) and result.update_text:
            if get_source_options().replace_announcement:
                from dialogs.local_announcement import show_local_announcement

                show_local_announcement(self.window())
                toast_success("发现新版本！", 2600)
                return
            try:
                import main_widget as _mw

                info = None
                if result.download_url and getattr(result, "download_sha256", ""):
                    info = {"url": result.download_url, "sha256": result.download_sha256}
                dialog = _mw.UpdateInfoDialog(result.update_text, self.window(), download_info=info)
                dialog.setModal(False)
                dialog.show()
                self._manual_update_dialog = dialog
                toast_success("发现新版本！", 2600)
            except Exception:
                self.logger.exception("打开更新弹窗失败")
                toast_info("发现新版本，请前往官网下载。", 3600)
            return
        toast_success(f"当前已是最新版本 v{VERSION}", 2800)


    def _open_onboarding_guide(self):
        """打开主窗口的三步上手引导（RN-110）。

        ⚠ 拿不到主窗口那个方法时**必须说话**：这个按钮就是给「不知道去哪儿设目录」
        的新用户准备的，它自己再没反应就等于把人扔在原地了。
        """
        from ui_toast import toast_warning

        opener = getattr(self.window(), "_show_onboarding_dialog", None)
        if not callable(opener):
            toast_warning("上手引导打不开，请到「工具与系统 - 高级设置」里选 CS2 目录。", 4200)
            return
        try:
            opener()
        except Exception:
            self.logger.exception("从关于页打开上手引导失败")
            toast_warning("上手引导打不开，请到「工具与系统 - 高级设置」里选 CS2 目录。", 4200)


    def _build_info_text(self):
        return f'''<p style='font-size: 14px; line-height: 1.8;'><b>作者：</b>孤帆<br><br>本工具通过监听 CS2 游戏状态接口 (GSI) 来实现击杀音效等功能。<br>请确保已正确选择 CS 文件夹 —— 本页下方的「{ONBOARDING_BUTTON_TEXT}」可以直接完成。<br><br>更多更新和内容进入群聊 <b>{SUPPORT_GROUP_ID}</b>，商业合作等进群加群主。<br><br><span style=\'color: {get_color('warning')};\'><b>免费软件 · 版权所有 · 严禁倒卖</b></span></p>'''


    def _sync_status_strip(self):
        detail_text = f'''当前安装版本：v{VERSION}\n运行渠道：桌面工具\n账号联动：已接入官网登录态识别\n更新与发布：以 {OFFICIAL_WEBSITE_URL} 返回结果为准'''
        badges = [
            ('info', f'''版本 · v{VERSION}'''),
            ('positive', '渠道 · 桌面工具'),
            ('warning', '账号 · 联动已接入')]
        render_badges(self.status_badge_label, badges, detail_tooltip = detail_text)
        self.summary_label.setText(detail_text)
        self.summary_label.setToolTip(detail_text)
        self.status_card.setToolTip(detail_text)
        self._sync_action_bar()


    def _open_website(self):
        QDesktopServices.openUrl(QUrl(OFFICIAL_WEBSITE_URL))


    def _sync_action_bar(self):
        if not hasattr(self, 'action_bar'):
            return
        loading = bool(self.current_loading_msg)
        options = get_source_options()
        self.action_bar.configure_secondary('打开官网', self._open_website, visible = True)
        notice_button = '查看本地公告' if options.replace_announcement else '查看更新日志'
        self.action_bar.configure_primary(notice_button, self._show_changelog, visible = True)
        self.action_bar.secondary_btn.setEnabled(not loading and not options.block_remote_network)
        self.action_bar.primary_btn.setEnabled(not loading and (options.replace_announcement or not options.block_remote_network))
        if options.block_remote_network:
            action_message = f"当前版本：v{VERSION} · {OFFLINE_MESSAGE}"
        elif options.replace_announcement:
            action_message = f"当前版本：v{VERSION} · 正在使用本地公告。"
        else:
            action_message = f'''当前版本：v{VERSION} · {'正在获取更新日志，请稍候' if loading else '可直接查看官网更新日志和公告'} · 官网与更新以 {OFFICIAL_WEBSITE_URL} 为准。'''
        self.action_bar.set_message(action_message)


    def _create_ui(self):
        '''创建UI'''
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setFrameShape(QFrame.NoFrame)
        page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page_widget = QWidget()
        layout = QVBoxLayout(page_widget)
        layout.setContentsMargins(16, 16, 16, 20)
        layout.setSpacing(12)
        from ui_help_panel import PAGE_HELP_TEXTS, install_help_panel
        header = PageHeader('关于软件', description = '看当前装的是哪个版本、有没有新版可更新。点右上角「?」看这一页各张卡管什么。', title_font_size = None, spacing = 12)
        self.page_lead_label = header.description_label
        layout.addWidget(header)
        install_help_panel(header.title_row, header.body, PAGE_HELP_TEXTS['about'])
        status_card = QFrame()
        status_card.setFrameShape(QFrame.StyledPanel)
        status_card.setObjectName('card')
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(14, 14, 14, 14)
        status_layout.setSpacing(10)
        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        status_title = QLabel('当前状态')
        status_title.setObjectName('statusLabel')
        status_row.addWidget(status_title)
        self.status_badge_label = create_badge_label()
        status_row.addWidget(self.status_badge_label, 1)
        status_row.addStretch()
        status_layout.addLayout(status_row)
        self.status_card = status_card
        self.summary_label = QLabel('')
        self.summary_label.setObjectName('hintLabel')
        self.summary_label.setWordWrap(True)
        self.summary_label.hide()
        status_layout.addWidget(self.summary_label)
        layout.addWidget(status_card)
        intro_card, intro_layout = SettingsCard.make('产品信息', '桌面端当前以安装状态、作者信息和产品说明为主，后续官网登录和联动能力也会继续沿这条线扩展。', margins = (14, 14, 14, 14), spacing = 10)
        logo_layout = QVBoxLayout()
        logo_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        logo_layout.setSpacing(4)
        logo_text = QLabel('帆派助手开放版')
        logo_text.setFont(QFont('Microsoft YaHei', 30, QFont.Bold))
        logo_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        logo_text.setObjectName('logoTitle')
        logo_layout.addWidget(logo_text)
        version_text = QLabel(f'''v{VERSION}''')
        version_text.setFont(QFont('Arial', 16))
        version_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        version_text.setObjectName('versionText')
        logo_layout.addWidget(version_text)
        intro_layout.addLayout(logo_layout)
        self.info_label = QLabel(self._build_info_text())
        self.info_label.setWordWrap(True)
        self.info_label.setTextFormat(Qt.RichText)
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.info_label.setObjectName('infoLabel')
        intro_layout.addWidget(self.info_label)
        setup_row = QHBoxLayout()
        setup_row.setSpacing(8)
        setup_hint = QLabel('还没设过 CS2 目录？其余功能全都依赖它。')
        setup_hint.setObjectName('hintLabel')
        setup_hint.setWordWrap(True)
        setup_row.addWidget(setup_hint, 1)
        self.goto_onboarding_button = QPushButton(ONBOARDING_BUTTON_TEXT)
        style_as_secondary_button(self.goto_onboarding_button)
        self.goto_onboarding_button.setFixedHeight(36)
        self.goto_onboarding_button.setMinimumWidth(132)
        self.goto_onboarding_button.setToolTip('打开选目录 / 写 GSI 配置 / 去试听的三步引导')
        self.goto_onboarding_button.clicked.connect(self._open_onboarding_guide)
        setup_row.addWidget(self.goto_onboarding_button, 0, Qt.AlignRight | Qt.AlignVCenter)
        intro_layout.addLayout(setup_row)
        layout.addWidget(intro_card)
        (update_card, update_layout) = SettingsCard.make('更新与渠道', f'''更新公告和发布包都以 {OFFICIAL_WEBSITE_URL} 的返回结果为准。''', margins = (14, 14, 14, 14), spacing = 10)
        check_row = QHBoxLayout()
        check_row.setSpacing(10)
        offline = get_source_options().block_remote_network
        release_hint = QLabel(OFFLINE_MESSAGE if offline else '软件每次启动会自动检查；也可以在这里手动检查一次。')
        release_hint.setObjectName('hintLabel')
        release_hint.setWordWrap(True)
        check_row.addWidget(release_hint, 1)
        self.check_update_button = QPushButton('立即检查更新')
        self.check_update_button.setEnabled(not offline)
        style_as_secondary_button(self.check_update_button)
        self.check_update_button.setFixedHeight(36)
        self.check_update_button.setMinimumWidth(132)
        self.check_update_button.clicked.connect(self._manual_check_update)
        check_row.addWidget(self.check_update_button)
        update_layout.addLayout(check_row)
        channel_label = QLabel(f'''官网：{OFFICIAL_WEBSITE_URL.replace('https://', '')}  |  社群：{SUPPORT_GROUP_ID}''')
        channel_label.setObjectName('hintLabel')
        channel_label.setWordWrap(True)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.addWidget(channel_label, 1)
        button_layout.addStretch()
        update_layout.addLayout(button_layout)
        layout.addWidget(update_card)
        (oss_card, oss_layout) = SettingsCard.make('开源与 Star', '帆派助手开放版的核心功能已经以 GPL-3.0 开源，代码在 GitHub 上可以逐行查看。', margins = (14, 14, 14, 14), spacing = 10)
        oss_ask = QLabel('如果这个软件帮到了你，<b>希望你能去仓库点一颗 Star ⭐</b>——这是对作者最直接的鼓励，也能让更多 CS2 玩家找到它。点过之后，GitHub 会在发布新版本时提醒你。')
        oss_ask.setObjectName('hintLabel')
        oss_ask.setWordWrap(True)
        oss_ask.setTextFormat(Qt.RichText)
        oss_layout.addWidget(oss_ask)
        oss_row = QHBoxLayout()
        oss_row.setSpacing(8)
        self.open_oss_button = QPushButton('去 GitHub 点 Star')
        style_as_secondary_button(self.open_oss_button)
        self.open_oss_button.setFixedHeight(36)
        self.open_oss_button.setMinimumWidth(148)
        self.open_oss_button.clicked.connect(self._open_opensource_repo)
        oss_row.addWidget(self.open_oss_button)
        self.copy_oss_button = QPushButton('复制仓库地址')
        style_as_secondary_button(self.copy_oss_button)
        self.copy_oss_button.setFixedHeight(36)
        self.copy_oss_button.clicked.connect(self._copy_opensource_repo)
        oss_row.addWidget(self.copy_oss_button)
        oss_row.addStretch()
        oss_layout.addLayout(oss_row)
        layout.addWidget(oss_card)
        (feedback_card, feedback_layout) = SettingsCard.make('反馈与求助', '遇到问题:先用「疑难杂症解决包」自己查一遍;还解决不了,再复制诊断信息到群里发出来。', margins = (14, 14, 14, 14), spacing = 10)
        kit_hint = QLabel('「帆派疑难杂症解决包」是免费的本机排障工具:把它交给你电脑上的 AI 助手,它会去读日志、看配置、定位问题,能修的当场修好,修不好会生成一份带证据的报告。<b>全程在你自己电脑上跑,不联网上传日志</b>,动手改任何东西之前都会先问你、先备份。')
        kit_hint.setObjectName('hintLabel')
        kit_hint.setWordWrap(True)
        kit_hint.setTextFormat(Qt.RichText)
        feedback_layout.addWidget(kit_hint)
        kit_row = QHBoxLayout()
        kit_row.setSpacing(8)
        self.open_help_kit_button = QPushButton('下载解决包')
        style_as_secondary_button(self.open_help_kit_button)
        self.open_help_kit_button.setFixedHeight(36)
        self.open_help_kit_button.clicked.connect(self._open_help_kit)
        kit_row.addWidget(self.open_help_kit_button)
        self.copy_help_kit_button = QPushButton('复制下载地址')
        style_as_secondary_button(self.copy_help_kit_button)
        self.copy_help_kit_button.setFixedHeight(36)
        self.copy_help_kit_button.clicked.connect(self._copy_help_kit)
        kit_row.addWidget(self.copy_help_kit_button)
        kit_row.addStretch()
        feedback_layout.addLayout(kit_row)
        fb_row = QHBoxLayout()
        fb_row.setSpacing(8)
        self.copy_group_button = QPushButton('复制群号')
        style_as_secondary_button(self.copy_group_button)
        self.copy_group_button.setFixedHeight(36)
        self.copy_group_button.clicked.connect(self._copy_support_group)
        fb_row.addWidget(self.copy_group_button)
        self.copy_diag_button = QPushButton('复制诊断信息')
        style_as_secondary_button(self.copy_diag_button)
        self.copy_diag_button.setFixedHeight(36)
        self.copy_diag_button.clicked.connect(self._copy_diagnostics)
        fb_row.addWidget(self.copy_diag_button)
        fb_row.addStretch()
        feedback_layout.addLayout(fb_row)
        layout.addWidget(feedback_card)
        layout.addStretch(1)
        page_scroll.setWidget(page_widget)
        outer.addWidget(page_scroll, 1)
        self.action_bar = PageActionBar(self)
        self.action_bar.secondary_btn.setMinimumWidth(116)
        self.action_bar.primary_btn.setMinimumWidth(132)
        outer.addWidget(self.action_bar, 0)
        self._sync_status_strip()


    def _copy_support_group(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(str(SUPPORT_GROUP_ID))
        try:
            from ui_toast import toast_success

            toast_success(f"群号已复制: {SUPPORT_GROUP_ID}")
        except Exception:
            pass


    def _open_opensource_repo(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(OPENSOURCE_REPO_URL))


    def _copy_opensource_repo(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(OPENSOURCE_REPO_URL)
        try:
            from ui_toast import toast_success

            toast_success("仓库地址已复制")
        except Exception:
            pass


    def _open_help_kit(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(HELP_KIT_URL))


    def _copy_help_kit(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(HELP_KIT_URL)
        try:
            from ui_toast import toast_success

            toast_success("解决包下载地址已复制")
        except Exception:
            pass


    def _collect_diagnostics(self) -> str:
        """汇总不含隐私的环境信息 + 脱敏日志尾部,方便贴群里排障。"""
        import platform
        import sys

        from config import VERSION, config

        lines = [
            f"帆派助手开放版 {VERSION}",
            f"系统: {platform.system()} {platform.release()} ({platform.machine()})",
            f"Python 运行时: {platform.python_version()}",
            f"安装形态: {'冻结(打包)' if getattr(sys, 'frozen', False) else '源码运行'}",
            f"主题: {getattr(config, 'ui_theme', 'dark')} | 字号: {int(float(getattr(config, 'ui_font_scale', 1.0)) * 100)}%",
            f"专家模式: {bool(getattr(config, 'ui_expert_mode', False))}",
        ]
        try:
            import ctypes
            lines.append(f"管理员: {bool(ctypes.windll.shell32.IsUserAnAdmin())}")
        except Exception:
            pass
        load_error = getattr(config, "_load_error", "")
        if load_error:
            lines.append(f"配置加载: {load_error}")
        try:
            # QA-011: 这里原本 `from gsi_server import get_gsi_server` —— 那个名字不存在，
            # 100% 抛 ImportError 被下面的裸 except 吞成「GSI: 未知」，用户复制出来的
            # 诊断信息里最该看的一行永远是空的。实例改从主窗口拿（main_widget.py 挂的），
            # 运行态走 collect_gsi_status 统一取，属性名不再在这里手写第二遍。
            # gsi_server 保持方法内局部 import：提到模块顶层会把 flask 拖进启动路径。
            from core.runtime.system_status_service import collect_gsi_status
            from gsi_server import get_active_port

            status = collect_gsi_status(self.window())
            if not status.get("available"):
                lines.append("GSI: 未初始化")
            else:
                state = "运行中" if status.get("running") else "未运行"
                line = f"GSI: {state} | 端口 {get_active_port()}"
                err = str(status.get("startup_error") or "")
                if err:
                    line += f" | 启动错误: {err}"
                lines.append(line)
        except Exception:
            lines.append("GSI: 未知")
        try:
            from core.diagnostics import read_recent_log_tail
            from core.utils.log_filter import redact_text
            from core.utils.logger import get_logger

            log_dir = str(getattr(get_logger(), "log_dir", "") or "")
            tail = read_recent_log_tail(log_dir, max_lines=40, redactor=redact_text)
            if tail:
                lines.append("")
                lines.append("最近日志(已脱敏):")
                lines.append(tail)
        except Exception:
            pass
        return "\n".join(lines)


    def _copy_diagnostics(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._collect_diagnostics())
        try:
            from ui_toast import toast_success

            toast_success("诊断信息已复制,直接粘贴到群里即可")
        except Exception:
            pass


    def _show_changelog(self):
        '''显示更新日志'''
        options = get_source_options()
        if options.replace_announcement:
            from dialogs.local_announcement import show_local_announcement

            show_local_announcement(self.window())
            return
        if options.block_remote_network:
            from ui_toast import toast_info

            toast_info(OFFLINE_MESSAGE)
            return
        loading_msg = QMessageBox(self)
        loading_msg.setWindowTitle('加载中')
        loading_msg.setText('正在获取更新日志，请稍候...')
        loading_msg.setStandardButtons(QMessageBox.NoButton)
        loading_msg.setModal(True)
        loading_msg.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        loading_msg.show()
        self.changelog_fetcher = ChangelogFetcher()
        self.current_loading_msg = loading_msg
        self.changelog_fetcher.finished.connect((lambda content: self._on_changelog_fetched(content)))
        self.changelog_fetcher.error.connect((lambda error: self._on_changelog_error(error)))
        self.changelog_fetcher.start()
        self._sync_action_bar()
        self.logger.info('开始获取更新日志')


    def _on_changelog_fetched(self, content):
        '''更新日志获取成功'''
        if hasattr(self, 'current_loading_msg') and self.current_loading_msg:
            try:
                self.current_loading_msg.close()
                self.current_loading_msg.deleteLater()
                self.current_loading_msg = None
            except Exception:
                pass
        dialog = ChangelogDialog(content, self)
        dialog.exec()
        self._sync_action_bar()
        self.logger.info('更新日志显示完成')


    def _on_changelog_error(self, error):
        '''更新日志获取失败'''
        if hasattr(self, 'current_loading_msg') and self.current_loading_msg:
            try:
                self.current_loading_msg.close()
                self.current_loading_msg.deleteLater()
                self.current_loading_msg = None
            except Exception:
                pass
        QMessageBox.critical(self, '错误', f'''获取更新日志失败！\n\n错误信息：{error}''')
        self._sync_action_bar()
        self.logger.error(f'''获取更新日志失败: {error}''')


    def _apply_theme_styles(self):
        '''主题变更时刷新内联样式'''
        if hasattr(self, 'info_label'):
            self.info_label.setText(self._build_info_text())


    def deleteLater(self):
        '''清理：注销主题回调'''
        from theme_manager import get_theme_manager
        get_theme_manager().unregister_theme_changed_callback(self._apply_theme_styles)
        super().deleteLater()
