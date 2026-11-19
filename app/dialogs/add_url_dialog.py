"""
在线音乐URL导入对话框
支持多平台音乐链接添加
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QWidget, QCheckBox, QMessageBox, QScrollArea, QFrame,
    QSizePolicy,
)
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from core.utils.logger import get_logger
from theme_manager import get_theme_manager


class URLTestThread(QThread):
    """后台测试URL线程"""
    result_ready = Signal(bool, str, object)

    def __init__(self, url, resolver, parent=None):
        super().__init__(parent)
        self.url = url
        self.resolver = resolver
        self.logger = get_logger()

    def run(self):
        """执行URL测试"""
        try:
            if self.resolver:
                success, message, info = self.resolver.test_url(self.url)
                self.result_ready.emit(success, message, info)
            else:
                self.result_ready.emit(False, 'URL解析器不可用', None)
        except Exception as e:
            self.logger.error(f"URL测试出错: {e}")
            self.result_ready.emit(False, f"测试出错: {str(e)}", None)




class CacheThread(QThread):
    """后台缓存下载线程"""
    cache_done = Signal(bool, str, object)

    def __init__(self, url, info, resolver, track, parent=None):
        super().__init__(parent)
        self.url = url
        self.info = info
        self.resolver = resolver
        self.track = track
        self.logger = get_logger()

    def run(self):
        """执行缓存下载"""
        try:
            if self.resolver:
                cache_path = self.resolver.download_to_cache(self.url, self.info)
                if cache_path:
                    self.logger.info(f"缓存成功: {cache_path}")
                    self.cache_done.emit(True, cache_path, self.track)
                else:
                    self.cache_done.emit(False, '缓存失败', self.track)
            else:
                self.cache_done.emit(False, 'URL解析器不可用', self.track)
        except Exception as e:
            self.logger.error(f"缓存下载出错: {e}")
            self.cache_done.emit(False, f"缓存失败: {str(e)}", self.track)



class AddURLDialog(QDialog):
    """添加在线音乐对话框"""

    def __init__(self, parent, player):
        super().__init__(parent)
        self.player = player
        self.logger = get_logger()
        self.current_info = None
        self.test_passed = False
        self.setWindowTitle('添加在线音乐')
        self.resize(750, 620)
        self.theme_manager = get_theme_manager()
        self.setStyleSheet(self.theme_manager.get_stylesheet())
        self.colors = self.theme_manager.current_theme.colors
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_add_tab(), '添加音乐')
        self.tabs.addTab(self._create_platforms_tab(), '支持平台')
        self.tabs.addTab(self._create_cache_tab(), '缓存管理')
        layout.addWidget(self.tabs)

    def _create_add_tab(self):
        """创建添加音乐选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        url_frame, url_layout = self._create_section_frame('URL地址')
        url_input_layout = QHBoxLayout()
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText('粘贴音乐链接或直接音频URL...')
        self.url_entry.setMinimumHeight(34)
        url_input_layout.addWidget(self.url_entry)
        test_btn = QPushButton('测试')
        test_btn.setObjectName('actionButton')
        test_btn.setFixedSize(68, 34)
        test_btn.clicked.connect(self._test_url)
        url_input_layout.addWidget(test_btn)
        url_layout.addLayout(url_input_layout)
        self.test_status_label = QLabel('')
        url_layout.addWidget(self.test_status_label)
        layout.addWidget(url_frame)
        info_frame, info_layout = self._create_section_frame('音乐信息')
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel('标题:'))
        self.title_entry = QLineEdit()
        self.title_entry.setPlaceholderText('歌曲标题...')
        title_layout.addWidget(self.title_entry)
        info_layout.addLayout(title_layout)
        artist_layout = QHBoxLayout()
        artist_layout.addWidget(QLabel('歌手:'))
        self.artist_entry = QLineEdit()
        self.artist_entry.setPlaceholderText('歌手名称...')
        artist_layout.addWidget(self.artist_entry)
        info_layout.addLayout(artist_layout)
        album_layout = QHBoxLayout()
        album_layout.addWidget(QLabel('专辑:'))
        self.album_entry = QLineEdit()
        self.album_entry.setPlaceholderText('专辑名称（可选）...')
        album_layout.addWidget(self.album_entry)
        info_layout.addLayout(album_layout)
        meta_layout = QHBoxLayout()
        meta_layout.addWidget(QLabel('时长:'))
        self.duration_label = QLabel('--:--')
        meta_layout.addWidget(self.duration_label)
        meta_layout.addStretch()
        meta_layout.addWidget(QLabel('来源:'))
        self.platform_label = QLabel('未知')
        meta_layout.addWidget(self.platform_label)
        info_layout.addLayout(meta_layout)
        layout.addWidget(info_frame)
        options_frame, options_layout = self._create_section_frame('选项')
        from config import config
        self.cache_var = QCheckBox('缓存到本地 (推荐，提高播放稳定性)')
        self.cache_var.setChecked(getattr(config, 'music_cache_enabled', True))
        options_layout.addWidget(self.cache_var)
        self.auto_fill_var = QCheckBox('自动填充歌曲信息')
        self.auto_fill_var.setChecked(True)
        options_layout.addWidget(self.auto_fill_var)
        layout.addWidget(options_frame)
        layout.addStretch()
        button_layout = QHBoxLayout()
        self.info_label = QLabel('')
        button_layout.addWidget(self.info_label)
        button_layout.addStretch()
        cancel_btn = QPushButton('取消')
        cancel_btn.setObjectName('secondaryButton')
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        self.add_btn = QPushButton('确认添加')
        self.add_btn.setObjectName('primaryButton')
        self.add_btn.setFixedWidth(100)
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self._add_url_track)
        button_layout.addWidget(self.add_btn)
        layout.addLayout(button_layout)
        return tab

    def _create_platforms_tab(self):
        """创建支持平台选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)
        title = QLabel('支持的音乐平台')
        title.setFont(QFont('', 16, QFont.Bold))
        scroll_layout.addWidget(title)
        if hasattr(self.player, 'url_resolver') and self.player.url_resolver:
            platforms = self.player.url_resolver.get_supported_platforms()
        else:
            platforms = [
                {'name': '直接链接', 'icon': '🔗', 'example': 'https://example.com/music.mp3'},
            ]

        for platform in platforms:
            platform_frame = QFrame()
            platform_frame.setFrameShape(QFrame.StyledPanel)
            platform_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            platform_layout = QVBoxLayout(platform_frame)
            name_label = QLabel(f"{platform['icon']} {platform['name']}")
            name_label.setFont(QFont('', 12, QFont.Bold))
            platform_layout.addWidget(name_label)
            example_layout = QHBoxLayout()
            example_layout.addWidget(QLabel('示例:'))
            example_entry = QLineEdit(platform['example'])
            example_entry.setReadOnly(True)
            example_layout.addWidget(example_entry)
            copy_btn = QPushButton('复制')
            copy_btn.clicked.connect(lambda checked, text=platform['example']: self._copy_to_clipboard(text))
            example_layout.addWidget(copy_btn)
            platform_layout.addLayout(example_layout)
            scroll_layout.addWidget(platform_frame)
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        return tab

    def _create_cache_tab(self):
        """创建缓存管理选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        info_frame, info_layout = self._create_section_frame('缓存信息')
        self.cache_size_label = QLabel('缓存大小: 计算中...')
        info_layout.addWidget(self.cache_size_label)
        self.cache_count_label = QLabel('缓存文件数: 计算中...')
        info_layout.addWidget(self.cache_count_label)
        layout.addWidget(info_frame)
        desc_label = QLabel('缓存说明:\n• 缓存文件存储在本地，避免重复下载\n• 某些平台（如网易云、B站）必须缓存才能播放\n• 清理缓存不会影响已添加到播放列表的歌曲')
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        layout.addStretch()
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        refresh_btn = QPushButton('刷新')
        refresh_btn.setObjectName('actionButton')
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self._update_cache_info)
        button_layout.addWidget(refresh_btn)
        clear_btn = QPushButton('清理缓存')
        clear_btn.setObjectName('dangerButton')
        clear_btn.setFixedWidth(100)
        clear_btn.clicked.connect(self._clear_cache)
        button_layout.addWidget(clear_btn)
        layout.addLayout(button_layout)
        self._update_cache_info()
        return tab

    def _create_section_frame(self, title):
        """创建区域框架，返回frame和内容布局"""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 10, 12, 10)
        frame_layout.setSpacing(8)
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        frame_layout.addWidget(title_label)
        return (frame, frame_layout)

    def _test_url(self):
        """测试URL"""
        from core.runtime.source_options import OFFLINE_MESSAGE, remote_network_blocked

        if remote_network_blocked():
            self._on_test_result(False, OFFLINE_MESSAGE, None)
            return
        url = self.url_entry.text().strip()
        if not url:
            self.test_status_label.setText('❌ 请输入URL')
            self.test_status_label.setStyleSheet(f"color: {self.colors.error}; font-weight: bold;")
            return
        self.test_status_label.setText('⏳ 测试中...')
        self.test_status_label.setStyleSheet(f"color: {self.colors.warning}; font-weight: bold;")
        self.add_btn.setEnabled(False)
        self.info_label.setText('正在测试URL...')
        if getattr(self, 'test_thread', None) and self.test_thread.isRunning():
            self.info_label.setText('上一次测试仍在进行中…')
            return
        if hasattr(self.player, 'url_resolver') and self.player.url_resolver:
            self.test_thread = URLTestThread(url, self.player.url_resolver, parent = self)
            self.test_thread.result_ready.connect(self._on_test_result)
            self.test_thread.start()
        else:
            self._on_test_result(False, 'URL解析器不可用', None)

    def _on_test_result(self, success, message, info):
        """处理测试结果"""
        if success:
            self.test_status_label.setText(f"✅ {message}")
            self.test_status_label.setStyleSheet(f"color: {self.colors.success}; font-weight: bold;")
            self.test_passed = True
            self.current_info = info
            self.add_btn.setEnabled(True)
            if info and self.auto_fill_var.isChecked():
                if info.get('title'):
                    self.title_entry.setText(info['title'])
                if info.get('artist'):
                    self.artist_entry.setText(info['artist'])
                if info.get('album'):
                    self.album_entry.setText(info['album'])
                duration = info.get('duration', 0)
                if duration > 0:
                    minutes = duration // 60
                    seconds = duration % 60
                    self.duration_label.setText(f'{minutes}:{seconds:02d}')
                else:
                    self.duration_label.setText('未知')

                platform_map = {
                    'direct': '直接链接',
                    'netease': '网易云音乐',
                    'qqmusic': 'QQ音乐',
                    'kugou': '酷狗音乐',
                    'bilibili_audio': 'B站音频',
                    'bilibili_video': 'B站视频',
                    'youtube': 'YouTube' }
                platform = platform_map.get(info.get('platform', ''), '未知')
                self.platform_label.setText(platform)
            self.info_label.setText('')
        else:
            self.test_status_label.setText(f"❌ {message}")
            self.test_status_label.setStyleSheet(f"color: {self.colors.error}; font-weight: bold;")
            self.test_passed = False
            self.current_info = None
            self.add_btn.setEnabled(False)
            self.info_label.setText('')

    def _add_url_track(self):
        """添加URL音轨"""
        if not self.test_passed:
            QMessageBox.warning(self, '提示', '请先测试URL是否有效')
            return

        url = self.url_entry.text().strip()
        title = self.title_entry.text().strip()
        if not url:
            QMessageBox.warning(self, '提示', '请输入URL地址')
            return
        if not title:
            title = self.current_info.get('title', '') if self.current_info else url.split('/')[-1]
            if not title:
                QMessageBox.warning(self, '提示', '请输入歌曲标题')
                return

        track = {
            'type': 'url',
            'path': url,
            'title': title,
            'artist': self.artist_entry.text().strip() or '未知艺术家',
            'album': self.album_entry.text().strip() or '',
            'duration': self.current_info.get('duration', 0) if self.current_info else 0,
        }
        platform = self.current_info.get('platform', '') if self.current_info else ''
        needs_cache = platform in ('netease', 'bilibili_video', 'bilibili_audio', 'qqmusic', 'kugou')

        if needs_cache or self.cache_var.isChecked():
            if needs_cache and not self.cache_var.isChecked():
                self.logger.info(f'平台 {platform} 需要缓存，自动启用缓存')
            self.info_label.setText('正在缓存...')
            self.add_btn.setEnabled(False)
            if getattr(self, 'cache_thread', None) and self.cache_thread.isRunning():
                self.info_label.setText('正在缓存，请稍候…')
                return
            if hasattr(self.player, 'url_resolver') and self.player.url_resolver:
                self.cache_thread = CacheThread(
                    url, self.current_info, self.player.url_resolver, track, parent=self,
                )
                self.cache_thread.cache_done.connect(self._on_cache_finished)
                self.cache_thread.start()
            else:
                QMessageBox.critical(self, '错误', 'URL解析器不可用')
        else:
            self._finish_add_track(track)

    def _on_cache_finished(self, success, result, track):
        """缓存完成回调"""
        if success:
            track['type'] = 'local'
            track['path'] = result
            track['original_url'] = self.url_entry.text().strip()
            self._finish_add_track(track)
        else:
            self.add_btn.setEnabled(True)
            self.info_label.setText('')
            QMessageBox.critical(self, '错误', f"缓存失败: {result}")

    def closeEvent(self, event):
        """关闭前等待后台线程结束，避免 QThread 随对话框销毁时仍在运行"""
        for attr in ('test_thread', 'cache_thread'):
            thread = getattr(self, attr, None)
            if thread and thread.isRunning():
                thread.wait(3000)
        super().closeEvent(event)

    def _finish_add_track(self, track):
        """完成添加音轨"""
        try:
            if 'title' not in track or not track['title']:
                track['title'] = '未知歌曲'
            if 'artist' not in track:
                track['artist'] = '未知艺术家'
            if 'duration' not in track:
                track['duration'] = 0

            self.logger.info(f"添加音轨: {track['title']} - {track['artist']}")
            self.player.add_track(track)
            QMessageBox.information(self, '成功', f"已添加歌曲:\n{track['title']} - {track['artist']}")
            self.accept()
        except Exception as e:
            self.logger.error(f"添加音轨失败: {e}")
            QMessageBox.critical(self, '错误', f"添加失败: {str(e)}")

    def _update_cache_info(self):
        """更新缓存信息"""
        if hasattr(self.player, 'url_resolver') and self.player.url_resolver:
            size = self.player.url_resolver.get_cache_size()
            count = self.player.url_resolver.get_cache_count()
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1048576:
                size_str = f"{size / 1024:.2f} KB"
            elif size < 1073741824:
                size_str = f"{size / 1048576:.2f} MB"
            else:
                size_str = f"{size / 1073741824:.2f} GB"
            self.cache_size_label.setText(f"缓存大小: {size_str}")
            self.cache_count_label.setText(f"缓存文件数: {count}")
        else:
            self.cache_size_label.setText('缓存大小: 不可用')
            self.cache_count_label.setText('缓存文件数: 不可用')

    def _clear_cache(self):
        """清理缓存"""
        reply = QMessageBox.question(self, '确认', '确定要清理所有缓存文件吗？\n这不会影响已添加到播放列表的歌曲。', QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if hasattr(self.player, 'url_resolver') and self.player.url_resolver:
                self.player.url_resolver.clear_cache()
                QMessageBox.information(self, '成功', '缓存已清理')
                self._update_cache_info()
            else:
                QMessageBox.warning(self, '提示', 'URL解析器不可用')

    def _copy_to_clipboard(self, text):
        """复制到剪贴板"""
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, '已复制', '示例链接已复制到剪贴板')
