"""Centralized public service endpoints for FanTool desktop."""

OFFICIAL_WEBSITE_URL = "https://fantool.online"
COMMUNITY_WEBSITE_URL = "https://community.fantool.online"

COMMUNITY_CATEGORY_IDS = {
    "kill_sound": 1,
    "kill_voice": 2,
    "reload_sound": 3,
    "switch_weapon": 4,
    "gun_sound": 5,
    "death_sound": 6,
    "kill_icon": 7,
    "special_sound": 22,
    "flash": 23,
}
COMMUNITY_CATEGORY_URLS = {
    key: f"{COMMUNITY_WEBSITE_URL}/category.php?id={cid}"
    for key, cid in COMMUNITY_CATEGORY_IDS.items()
}
COMMUNITY_KILL_ICON_URL = COMMUNITY_CATEGORY_URLS["kill_icon"]

OPENSOURCE_REPO_URL = "https://github.com/gufan0000/cs2-customizer"
HELP_KIT_URL = "https://pan.quark.cn/s/384d775b069f"
SUPPORT_GROUP_ID = "891346430"
SUPPORT_BILIBILI_NAME = "\u5b64\u5e06233"
SUPPORT_BILIBILI_SEARCH_URL = "https://search.bilibili.com/all?keyword=%E5%AD%A4%E5%B8%86233"
SUPPORT_APP_SEARCH_KEYWORD = "\u5e06\u6d3e\u52a9\u624b"
SUPPORT_APP_SEARCH_URL = "https://www.baidu.com/s?wd=%E5%B8%86%E6%B4%BE%E5%8A%A9%E6%89%8B"

CLIENT_UPDATE_API_URL = f"{OFFICIAL_WEBSITE_URL}/api/client_update.php"
CHANGELOG_API_URL = f"{OFFICIAL_WEBSITE_URL}/api/get_changelog.php"
ACCOUNT_SERVICE_BASE_URL = OFFICIAL_WEBSITE_URL

ACCOUNT_REGISTER_URL = f"{OFFICIAL_WEBSITE_URL}/auth/register.html"
DEFAULT_COMMUNITY_TRACK_URL = f"{COMMUNITY_WEBSITE_URL}/music/cs%E7%9A%84lemon.mp3"
