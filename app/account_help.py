# Source Generated with Decompyle++
# File: C:\baidunetdiskdownload\Fantool\_work\v2.3.0\extracted_installed\app_2.3.0.exe_extracted\PYZ.pyz_extracted\account_help.pyc (Python 3.13)

'''账号页的帮助文案。**独立成一个模块，是为了让开源版不带它。**

## 为什么不直接写在 `ui_help_panel.PAGE_HELP_TEXTS` 里

原来就写在那里，靠 `build_tools/oss_sync/patches/ui_help_panel_py.patch`
在同步时把那一段删掉。而那个补丁**只做一件事：删这一段**，其余全是上下文 ——
于是上游每改一次这张表附近的字（批 49 补了三页文案、批 51 改了两个导航名），
补丁就整条打不上，同步被卡死。RN-510 为此收了三轮税。

⇒ 照 `build_tools/oss_sync/README.md` 那条规矩办：
**把那块代码改成结构上可选（独立模块 + 能力检查），然后把补丁删掉。**
开源版的排除清单里已经有 `account_auth_client.py` / `pages/account_page.py`，
这个文件跟着它们一起不进开源版；`ui_help_panel` 导不到就自然没有这一条。

⭐ 补丁集应该随时间趋近于零 —— 这是第一笔真正减下去的。
'''
ACCOUNT_HELP_TEXT = '<b>功能说明</b><br>用官网账号登录，桌面端会保持在线状态、会话到期前自动续期。<br><br><b>现在能用</b><br>• 显示登录状态与会话有效期<br>• 一键直达官网通知 / 版本公告<br><br><b>规划中（尚未上线）</b><br>• 跨设备的云端配置同步<br>• 付费 / 激活相关能力<br><br><b>注意事项</b><br>• 不登录也能正常使用软件的全部现有功能，登录只是为了上面这些附加能力'
