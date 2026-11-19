import re
import requests
import os
import hashlib
import json
import threading
import time
import uuid
from urllib.parse import urlparse
from typing import Optional, Dict, List, Tuple
from core.utils.logger import get_logger
from core.io_validation import replace_with_retry

logger = get_logger('URLResolver')

class URLResolver:
    """URL解析器基类"""

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def can_resolve(self, url: str) -> bool:
        """检查是否可以解析此URL"""
        raise NotImplementedError

    def resolve(self, url: str) -> Optional[Dict]:
        """解析URL并返回音频信息"""
        raise NotImplementedError

    def test_availability(self, url: str) -> Tuple[bool, str]:
        """测试URL是否可用"""
        try:
            info = self.resolve(url)
            if info and info.get('url'):
                audio_url = info['url']
                response = requests.head(audio_url, headers=self.headers, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    return True, '链接有效'
                else:
                    return False, f'音频链接返回状态码: {response.status_code}'
            return False, '无法解析URL'
        except Exception as e:
            return False, f'测试失败: {str(e)}'

    def get_cache_path(self, url: str) -> str:
        """获取缓存文件路径"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(self.cache_dir, f'{url_hash}.cache')



class DirectURLResolver(URLResolver):
    """直接音频URL解析器"""

    def can_resolve(self, url: str) -> bool:
        """检查是否是直接的音频URL"""
        audio_extensions = ['.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac', '.opus', '.webm']
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        return any(path.endswith(ext) for ext in audio_extensions)

    def resolve(self, url: str) -> Optional[Dict]:
        """解析直接URL"""
        try:
            response = requests.head(url, headers=self.headers, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                filename = os.path.basename(urlparse(url).path)
                if not filename:
                    filename = 'Unknown'
                content_disposition = response.headers.get('Content-Disposition', '')
                if 'filename=' in content_disposition:
                    filename = content_disposition.split('filename=')[-1].strip('"')
                return {
                    'url': url,
                    'title': os.path.splitext(filename)[0],
                    'artist': 'Unknown',
                    'duration': 0,
                    'direct': True,
                    'size': int(response.headers.get('Content-Length', 0)),
                }
        except Exception:
            pass
        return None







class NeteaseMusicResolver(URLResolver):
    """网易云音乐解析器"""

    def can_resolve(self, url: str) -> bool:
        """检查是否是网易云音乐链接"""
        patterns = [r'music\.163\.com', r'y\.music\.163\.com']
        return any(re.search(pattern, url) for pattern in patterns)

    def resolve(self, url: str) -> Optional[Dict]:
        """解析网易云音乐链接"""
        song_id = None
        patterns = [r'id=(\d+)', r'song/(\d+)', r'/(\d+)\.html']
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                song_id = match.group(1)
                break
        if not song_id:
            return None

        try:
            detail_api = f'https://music.163.com/api/song/detail/?id={song_id}&ids=[{song_id}]'
            response = requests.get(detail_api, headers=self.headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('songs') and len(data['songs']) > 0:
                    song_info = data['songs'][0]
                    audio_url = f'https://music.163.com/song/media/outer/url?id={song_id}.mp3'
                    return {
                        'url': audio_url,
                        'title': song_info.get('name', f'网易云音乐 - {song_id}'),
                        'artist': ', '.join([artist.get('name', '') for artist in song_info.get('artists', [])]),
                        'duration': song_info.get('duration', 0) // 1000,
                        'album': song_info.get('album', {}).get('name', ''),
                        'cover': song_info.get('album', {}).get('picUrl', ''),
                        'direct': False,
                        'platform': 'netease',
                        'headers': {
                            'Referer': 'https://music.163.com',
                            'User-Agent': self.headers['User-Agent'],
                        },
                    }
        except Exception as e:
            logger.error(f'网易云音乐解析失败: {e}')

        return {
            'url': f'https://music.163.com/song/media/outer/url?id={song_id}.mp3',
            'title': f'网易云音乐 - {song_id}',
            'artist': 'Unknown',
            'duration': 0,
            'direct': False,
            'platform': 'netease',
            'headers': {
                'Referer': 'https://music.163.com',
                'User-Agent': self.headers['User-Agent'],
            },
        }




















class QQMusicResolver(URLResolver):
    """QQ音乐解析器 - 改进版"""

    def can_resolve(self, url: str) -> bool:
        """检查是否是QQ音乐链接"""
        patterns = [r'y\.qq\.com', r'music\.qq\.com', r'i\.y\.qq\.com']
        return any(re.search(pattern, url) for pattern in patterns)

    def resolve(self, url: str) -> Optional[Dict]:
        """解析QQ音乐链接"""
        song_mid = None
        patterns = [r'songmid=([0-9A-Za-z]+)', r'/([0-9A-Za-z]{14})\.html', r'song/([0-9A-Za-z]+)', r'mid=([0-9A-Za-z]+)']
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                song_mid = match.group(1)
                break
        if not song_mid:
            return None

        try:
            detail_api = 'https://u.y.qq.com/cgi-bin/musicu.fcg'
            req_data = {
                'comm': {
                    'cv': 4747474,
                    'ct': 24,
                    'format': 'json',
                    'inCharset': 'utf-8',
                    'outCharset': 'utf-8',
                    'notice': 0,
                    'platform': 'yqq.json',
                    'needNewCode': 1,
                    'uin': 0,
                    'g_tk_new_20200303': 5381,
                    'g_tk': 5381,
                },
                'req_1': {
                    'module': 'music.pf_song_detail_svr',
                    'method': 'get_song_detail_yqq',
                    'param': {
                        'song_mid': song_mid,
                        'song_type': 0,
                    },
                },
            }
            headers = self.headers.copy()
            headers.update({
                'Referer': 'https://y.qq.com/',
                'Origin': 'https://y.qq.com',
            })
            response = requests.post(
                detail_api,
                json=req_data,
                headers=headers,
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('req_1', {}).get('code') == 0:
                    song_info = data['req_1']['data']['track_info']
                    title = song_info.get('name', f'QQ音乐 - {song_mid}')
                    singers = song_info.get('singer', [])
                    artist = ', '.join([s.get('name', '') for s in singers]) if singers else 'Unknown'
                    album = song_info.get('album', {}).get('name', '')
                    duration = song_info.get('interval', 0)
                    return {
                        'url': f'https://y.qq.com/n/ryqq/songDetail/{song_mid}',
                        'title': title,
                        'artist': artist,
                        'duration': duration,
                        'album': album,
                        'direct': False,
                        'platform': 'qqmusic',
                        'song_mid': song_mid,
                        'need_vip': True,
                        'notice': 'QQ音乐需要会员才能播放完整歌曲',
                    }
        except Exception as e:
            logger.error(f'QQ音乐解析失败: {e}')
        return None






























class KugouMusicResolver(URLResolver):
    """酷狗音乐解析器 - 改进版"""

    def can_resolve(self, url: str) -> bool:
        """检查是否是酷狗音乐链接"""
        patterns = [r'kugou\.com', r'kg\.qq\.com', r'5sing\.kugou\.com']
        return any(re.search(pattern, url) for pattern in patterns)

    def resolve(self, url: str) -> Optional[Dict]:
        """解析酷狗音乐链接"""
        hash_match = re.search(r'hash=([A-F0-9]+)', url)
        album_id_match = re.search(r'album_id=(\d+)', url)
        if not hash_match:
            return None
        song_hash = hash_match.group(1)
        album_id = album_id_match.group(1) if album_id_match else ''
        try:
            api_url = 'https://wwwapi.kugou.com/yy/index.php'
            params = {
                'r': 'play/getdata',
                'hash': song_hash,
                'album_id': album_id,
                'dfid': '1qIhOa0bPDhS0UWIla3d5BcC',
                'mid': '0',
                'platid': 4,
                'from': 'web',
            }
            response = requests.get(api_url, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 1 and data.get('data'):
                    song_data = data['data']
                    play_url = song_data.get('play_url', '')
                    if not play_url:
                        play_url = song_data.get('play_backup_url', '')
                    if play_url:
                        return {
                            'url': play_url,
                            'title': song_data.get('song_name', f'酷狗音乐 - {song_hash[:8]}'),
                            'artist': song_data.get('author_name', 'Unknown'),
                            'duration': song_data.get('timelength', 0) // 1000,
                            'album': song_data.get('album_name', ''),
                            'cover': song_data.get('img', ''),
                            'lyrics': song_data.get('lyrics', ''),
                            'direct': False,
                            'platform': 'kugou',
                            'bitrate': song_data.get('bitrate', 128),
                        }
                    return {
                        'url': '',
                        'title': song_data.get('song_name', f'酷狗音乐 - {song_hash[:8]}'),
                        'artist': song_data.get('author_name', 'Unknown'),
                        'error': '需要VIP才能播放',
                        'platform': 'kugou',
                    }
        except Exception as e:
            logger.error(f'酷狗音乐解析失败: {e}')
        return None




















class BilibiliResolver(URLResolver):
    """Bilibili解析器"""

    def can_resolve(self, url: str) -> bool:
        """检查是否是Bilibili链接"""
        patterns = [r'bilibili\.com/video/', r'b23\.tv/', r'bilibili\.com/audio/']
        return any(re.search(pattern, url) for pattern in patterns)

    def resolve(self, url: str) -> Optional[Dict]:
        """解析Bilibili链接"""
        bv_match = re.search(r'BV[\w]+', url)
        av_match = re.search(r'av(\d+)', url)
        au_match = re.search(r'au(\d+)', url)
        if au_match:
            audio_id = au_match.group(1)
            return self._resolve_bilibili_audio(audio_id)
        elif bv_match or av_match:
            return self._resolve_bilibili_video(url)
        return None

    def _resolve_bilibili_audio(self, audio_id: str) -> Optional[Dict]:
        """解析B站音频"""
        try:
            api_url = f'https://www.bilibili.com/audio/music-service-c/web/song/info?sid={audio_id}'
            response = requests.get(api_url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0 and data.get('data'):
                    audio_data = data['data']
                    play_url_api = f'https://www.bilibili.com/audio/music-service-c/web/url?sid={audio_id}'
                    play_response = requests.get(play_url_api, headers=self.headers, timeout=5)
                    play_url = ''
                    if play_response.status_code == 200:
                        play_data = play_response.json()
                        if play_data.get('code') == 0:
                            play_url = play_data.get('data', {}).get('cdns', [''])[0]
                    return {
                        'url': play_url,
                        'title': audio_data.get('title', f'B站音频 - {audio_id}'),
                        'artist': audio_data.get('author', 'Unknown'),
                        'duration': audio_data.get('duration', 0),
                        'cover': audio_data.get('cover', ''),
                        'direct': False,
                        'platform': 'bilibili_audio',
                    }
        except Exception as e:
            logger.error(f'B站音频解析失败: {e}')
        return None

    def _resolve_bilibili_video(self, url: str) -> Optional[Dict]:
        """解析B站视频（提取音频）"""
        try:
            bv_match = re.search(r'BV[\w]+', url)
            av_match = re.search(r'av(\d+)', url)
            if bv_match:
                video_id = bv_match.group(0)
            elif av_match:
                video_id = f'av{av_match.group(1)}'
            else:
                return None

            info_api = f'https://api.bilibili.com/x/web-interface/view?bvid={video_id}' if bv_match else f'https://api.bilibili.com/x/web-interface/view?aid={av_match.group(1)}'
            info_response = requests.get(info_api, headers=self.headers, timeout=10)
            if info_response.status_code != 200:
                return None
            info_data = info_response.json()
            if info_data.get('code') != 0:
                return None
            video_data = info_data.get('data', {})
            cid = video_data.get('cid')
            if not cid:
                return None

            play_api = f'https://api.bilibili.com/x/player/playurl?bvid={video_id}&cid={cid}&fnval=16' if bv_match else f'https://api.bilibili.com/x/player/playurl?avid={av_match.group(1)}&cid={cid}&fnval=16'
            play_response = requests.get(play_api, headers=self.headers, timeout=10)
            if play_response.status_code != 200:
                return None
            play_data = play_response.json()
            if play_data.get('code') != 0:
                return None

            dash_data = play_data.get('data', {}).get('dash', {})
            audio_streams = dash_data.get('audio', [])
            if audio_streams:
                best_audio = max(audio_streams, key=lambda x: x.get('bandwidth', 0))
                audio_url = best_audio.get('baseUrl') or best_audio.get('base_url')
                if audio_url:
                    return {
                        'url': audio_url,
                        'title': video_data.get('title', f'B站视频 - {video_id}'),
                        'artist': video_data.get('owner', {}).get('name', 'Bilibili'),
                        'duration': video_data.get('duration', 0),
                        'cover': video_data.get('pic', ''),
                        'description': video_data.get('desc', ''),
                        'view_count': video_data.get('stat', {}).get('view', 0),
                        'direct': False,
                        'platform': 'bilibili_video',
                        'quality': f"{best_audio.get('bandwidth', 0) // 1000}kbps",
                        'headers': {
                            'Referer': 'https://www.bilibili.com',
                            'User-Agent': self.headers['User-Agent'],
                        },
                    }

            durl = play_data.get('data', {}).get('durl', [])
            if durl:
                video_url = durl[0].get('url')
                if video_url:
                    return {
                        'url': video_url,
                        'title': video_data.get('title', f'B站视频 - {video_id}'),
                        'artist': video_data.get('owner', {}).get('name', 'Bilibili'),
                        'duration': video_data.get('duration', 0),
                        'cover': video_data.get('pic', ''),
                        'direct': False,
                        'platform': 'bilibili_video',
                        'need_extract_audio': True,
                        'headers': {
                            'Referer': 'https://www.bilibili.com',
                            'User-Agent': self.headers['User-Agent'],
                        },
                    }
        except Exception as e:
            logger.error(f'B站视频解析失败: {e}')
        return None



































class YouTubeResolver(URLResolver):
    """YouTube解析器（需要yt-dlp）"""

    def __init__(self, cache_dir: str):
        super().__init__(cache_dir)
        self.yt_dlp_available = False
        self.yt_dlp = None
        try:
            import yt_dlp
            self.yt_dlp = yt_dlp
            self.yt_dlp_available = True
            logger.info('yt-dlp已加载')
        except ImportError:
            logger.warning('yt-dlp未安装，YouTube解析功能不可用')

    def can_resolve(self, url: str) -> bool:
        """检查是否是YouTube链接"""
        if not self.yt_dlp_available:
            return False
        patterns = [
            r'youtube\.com/watch\?v=',
            r'youtu\.be/',
            r'youtube\.com/embed/',
            r'music\.youtube\.com/',
            r'youtube\.com/shorts/',
        ]
        return any(re.search(pattern, url) for pattern in patterns)

    def resolve(self, url: str) -> Optional[Dict]:
        """解析YouTube链接"""
        if not self.yt_dlp_available or not self.yt_dlp:
            return None
        try:
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'youtube_include_dash_manifest': False,
                'no_check_certificate': True,
                'ignoreerrors': False,
                'logtostderr': False,
                'no_color': True,
                'noplaylist': True,
            }
            with self.yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f'正在解析YouTube链接: {url}')
                info = ydl.extract_info(url, download=False)
                if info:
                    audio_url = None
                    best_quality = 0
                    audio_ext = 'mp3'
                    formats = info.get('formats', [])
                    audio_formats = []
                    for fmt in formats:
                        if fmt.get('vcodec') == 'none' or fmt.get('acodec') != 'none':
                            audio_formats.append(fmt)

                    audio_formats.sort(key=lambda x: x.get('abr', 0) or x.get('tbr', 0), reverse=True)
                    if audio_formats:
                        best_format = audio_formats[0]
                        audio_url = best_format.get('url')
                        best_quality = best_format.get('abr', 0) or best_format.get('tbr', 0)
                        audio_ext = best_format.get('ext', 'mp3')
                        logger.info(f'找到音频格式: {audio_ext}, 比特率: {best_quality}kbps')

                    if not audio_url:
                        audio_url = info.get('url')
                        logger.info('使用默认格式')
                    if audio_url:
                        return {
                            'url': audio_url,
                            'title': info.get('title', 'Unknown'),
                            'artist': info.get('uploader', 'Unknown') or info.get('channel', 'Unknown'),
                            'duration': info.get('duration', 0),
                            'thumbnail': info.get('thumbnail'),
                            'description': info.get('description', ''),
                            'view_count': info.get('view_count', 0),
                            'like_count': info.get('like_count', 0),
                            'upload_date': info.get('upload_date', ''),
                            'direct': True,
                            'platform': 'youtube',
                            'quality': f'{best_quality}kbps' if best_quality else 'unknown',
                            'ext': audio_ext,
                            'youtube_id': info.get('id', ''),
                            'webpage_url': info.get('webpage_url', url),
                        }
                else:
                    logger.error('yt-dlp未能提取信息')
        except Exception as e:
            logger.error(f'YouTube解析失败: {e}', exc_info=True)
        return None

    def test_availability(self, url: str) -> Tuple[bool, str]:
        """测试YouTube链接是否可用"""
        if not self.yt_dlp_available:
            return False, 'yt-dlp未安装，请先运行: pip install yt-dlp'
        try:
            result = self.resolve(url)
            if result:
                return True, 'YouTube视频解析成功'
            else:
                return False, '无法解析YouTube视频'
        except Exception as e:
            return False, f'解析失败: {str(e)}'



















class SpotifyResolver(URLResolver):
    """Spotify解析器（基础实现）"""

    def can_resolve(self, url: str) -> bool:
        """检查是否是Spotify链接"""
        patterns = [
            r'spotify\.com/track/',
            r'spotify\.com/album/',
            r'spotify\.com/playlist/',
            r'open\.spotify\.com/',
        ]
        return any(re.search(pattern, url) for pattern in patterns)

    def resolve(self, url: str) -> Optional[Dict]:
        """解析Spotify链接"""
        track_match = re.search(r'track/([a-zA-Z0-9]+)', url)
        if not track_match:
            return None
        track_id = track_match.group(1)
        return {
            'url': '',
            'title': f'Spotify Track - {track_id}',
            'artist': 'Unknown',
            'platform': 'spotify',
            'error': 'Spotify需要授权才能播放，暂不支持直接播放',
            'spotify_id': track_id,
            'notice': '建议使用其他平台的链接，或下载后使用本地文件',
        }








class MusicURLResolver:
    """音乐URL解析器管理器"""

    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.resolvers = [
            DirectURLResolver(cache_dir),
            NeteaseMusicResolver(cache_dir),
            QQMusicResolver(cache_dir),
            KugouMusicResolver(cache_dir),
            BilibiliResolver(cache_dir),
            YouTubeResolver(cache_dir),
            SpotifyResolver(cache_dir),
        ]
        self.cache_file = os.path.join(cache_dir, 'url_cache.json')
        self._cache_lock = threading.Lock()
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """加载缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_cache(self):
        """保存缓存（调用方需持有 _cache_lock 或容忍最后写入者胜出）"""
        try:
            with self._cache_lock:
                data = json.dumps(self.cache, ensure_ascii=False, indent=2)
            tmp = f'{self.cache_file}.{uuid.uuid4().hex[:8]}.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(data)
            replace_with_retry(tmp, self.cache_file)
        except Exception:
            pass

    def get_supported_platforms(self) -> List[Dict]:
        """获取支持的平台列表"""
        platforms = [
            {'name': '直接链接', 'example': 'https://example.com/music.mp3', 'icon': '🔗'},
            {'name': '网易云音乐', 'example': 'https://music.163.com/#/song?id=123456', 'icon': '🎵'},
            {'name': 'QQ音乐', 'example': 'https://y.qq.com/n/ryqq/songDetail/001234', 'icon': '🎶'},
            {'name': '酷狗音乐', 'example': 'https://www.kugou.com/song/#hash=xxx', 'icon': '🎸'},
            {'name': 'Bilibili', 'example': 'https://www.bilibili.com/audio/au123456', 'icon': '📺'},
        ]
        for resolver in self.resolvers:
            if isinstance(resolver, YouTubeResolver) and resolver.yt_dlp_available:
                platforms.append({
                    'name': 'YouTube',
                    'example': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                    'icon': '📹',
                })
                break
        platforms.append({
            'name': 'Spotify (仅识别)',
            'example': 'https://open.spotify.com/track/xxx',
            'icon': '🎧',
        })
        return platforms

    def test_url(self, url: str) -> Tuple[bool, str, Optional[Dict]]:
        """测试URL并返回结果"""
        cache_key = hashlib.md5(url.encode()).hexdigest()
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if time.time() - cached_data.get('timestamp', 0) < 86400:
                return True, '已缓存', cached_data.get('info')

        for resolver in self.resolvers:
            if resolver.can_resolve(url):
                try:
                    info = resolver.resolve(url)
                    if info:
                        if info.get('error'):
                            return False, info.get('error'), info
                        if info.get('need_parse'):
                            return True, f"需要额外解析 ({info.get('platform', 'unknown')})", info
                        if info.get('need_extract_audio'):
                            return False, '需要从视频提取音频（暂不支持）', info

                        audio_url = info.get('url')
                        if audio_url:
                            headers = {'User-Agent': 'Mozilla/5.0'}
                            if 'headers' in info:
                                headers.update(info['headers'])
                            response = requests.head(
                                audio_url,
                                headers=headers,
                                timeout=5,
                                allow_redirects=True,
                            )
                            if response.status_code == 200:
                                self.cache[cache_key] = {
                                    'info': info,
                                    'timestamp': time.time(),
                                }
                                self._save_cache()
                                return True, f"解析成功 ({info.get('platform', 'direct')})", info
                            else:
                                return False, f'音频链接不可用 (HTTP {response.status_code})', info
                        else:
                            if info.get('platform') == 'spotify':
                                return False, info.get('notice', '不支持的平台'), info
                            return False, '未能获取音频链接', info
                except Exception as e:
                    return False, f'解析出错: {str(e)}', None
        return False, '不支持的URL格式', None

    def resolve(self, url: str) -> Optional[Dict]:
        """解析URL"""
        cache_key = hashlib.md5(url.encode()).hexdigest()
        if cache_key in self.cache:
            cached_data = self.cache[cache_key]
            if time.time() - cached_data.get('timestamp', 0) < 86400:
                return cached_data.get('info')
        for resolver in self.resolvers:
            if resolver.can_resolve(url):
                result = resolver.resolve(url)
                if result:
                    if result.get('url') and not result.get('error'):
                        with self._cache_lock:
                            self.cache[cache_key] = {
                                'info': result,
                                'timestamp': time.time(),
                            }
                        self._save_cache()
                    return result
        return None

    def download_to_cache(self, url: str, info: Dict) -> Optional[str]:
        """下载音频到缓存"""
        if not info:
            return None
        if info.get('platform') == 'spotify' or info.get('error'):
            return None

        url_hash = hashlib.md5(url.encode()).hexdigest()
        platform = info.get('platform', '')
        audio_url = info.get('url', '')
        ext = '.mp3'
        if platform == 'bilibili_video':
            ext = '.m4a'
        elif platform == 'bilibili_audio':
            ext = '.m4a'
        elif platform == 'netease':
            ext = '.mp3'
        elif platform == 'youtube':
            ext = f".{info.get('ext', 'mp3')}"
        else:
            if audio_url:
                parsed = urlparse(audio_url)
                path = parsed.path.lower()
                for extension in ('.mp3', '.m4a', '.flac', '.wav', '.aac', '.opus'):
                    if path.endswith(extension):
                        ext = extension
                        break

        cache_path = os.path.join(self.cache_dir, f'{url_hash}{ext}')
        if os.path.exists(cache_path):
            file_size = os.path.getsize(cache_path)
            if file_size > 1000:
                logger.info(f'使用已缓存文件: {cache_path} (大小: {file_size} 字节)')
                return cache_path
            else:
                os.remove(cache_path)
                logger.warning(f'删除无效缓存文件: {cache_path} (大小: {file_size} 字节)')

        if info.get('need_parse'):
            return None
        if info.get('need_extract_audio'):
            logger.info('需要从视频中提取音频，暂不支持')
            return None
        audio_url = info.get('url')
        if not audio_url:
            return None

        try:
            logger.info(f"开始下载: {info.get('title', 'Unknown')}")
            logger.info(f'音频URL: {audio_url}')
            logger.info(f'目标格式: {ext}')
            logger.info(f'平台: {platform}')
            headers = self.headers.copy()
            if 'headers' in info:
                headers.update(info['headers'])
            logger.info(f'请求头: {headers}')
            response = requests.get(
                audio_url,
                stream=True,
                timeout=30,
                headers=headers,
                allow_redirects=True,
            )
            logger.info(f'响应状态码: {response.status_code}')
            logger.info(f"响应头Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            logger.info(f"响应头Content-Length: {response.headers.get('Content-Length', 'Unknown')}")

            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                logger.error('错误: 返回的是HTML页面而不是音频文件')
                error_content = response.content[:500].decode('utf-8', errors='ignore')
                logger.error(f'HTML内容预览: {error_content}')
                return None
            response.raise_for_status()

            total_size = int(response.headers.get('Content-Length', 0))
            downloaded = 0
            max_download_bytes = 104857600
            if total_size > max_download_bytes:
                logger.error(f'取消下载: 文件声明大小 {total_size / 1048576:.0f}MB 超过上限 100MB')
                return None
            temp_path = f'{cache_path}.{uuid.uuid4().hex[:8]}.tmp'

            with open(temp_path, 'wb') as f:
                first_chunk = True
                last_logged_bucket = -1
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        if first_chunk:
                            logger.info(f'文件开头字节: {chunk[:16].hex()}')
                            first_chunk = False
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > max_download_bytes:
                            logger.error('取消下载: 实际数据量超过 100MB 上限')
                            try:
                                f.close()
                                os.remove(temp_path)
                            except OSError:
                                pass
                            return None
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_bucket = int(progress // 10)
                            if progress_bucket != last_logged_bucket:
                                logger.info(f'下载进度: {progress:.1f}%')
                                last_logged_bucket = progress_bucket

            logger.info(f'\n下载完成，文件大小: {downloaded} 字节')
            if downloaded < 1000:
                logger.error(f'错误: 下载的文件太小 ({downloaded} 字节)，可能不是有效的音频文件')
                if os.path.exists(temp_path):
                    with open(temp_path, 'rb') as f:
                        content = f.read(200)
                        try:
                            text_content = content.decode('utf-8', errors='ignore')
                            logger.info(f'文件内容: {text_content}')
                        except Exception:
                            logger.info(f'文件内容(hex): {content.hex()}')
                    os.remove(temp_path)
                return None

            actual_ext = self._detect_audio_format(temp_path)
            if actual_ext:
                logger.info(f'检测到实际格式: {actual_ext}')
                if actual_ext != ext:
                    new_cache_path = os.path.join(self.cache_dir, f'{url_hash}{actual_ext}')
                    replace_with_retry(temp_path, new_cache_path)
                    cache_path = new_cache_path
                else:
                    replace_with_retry(temp_path, cache_path)
            else:
                logger.warning('警告: 无法检测文件格式，使用默认扩展名')
                replace_with_retry(temp_path, cache_path)

            logger.info(f'保存完成: {cache_path}')
            meta_path = cache_path + '.json'
            meta_info = info.copy()
            meta_info.pop('headers', None)
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta_info, f, ensure_ascii=False, indent=2)
            return cache_path
        except Exception as e:
            logger.error(f'\n下载失败: {e}', exc_info=True)
            if 'temp_path' in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
        return None

    def _detect_audio_format(self, file_path: str) -> Optional[str]:
        """通过文件头检测音频格式"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
            if header[:3] == b'ID3' or header[:2] == b'\xff\xfb':
                return '.mp3'
            elif header[4:8] == b'ftyp':
                return '.m4a'
            elif header[:4] == b'fLaC':
                return '.flac'
            elif header[:4] == b'OggS':
                return '.ogg'
            elif header[:4] == b'RIFF' and header[8:12] == b'WAVE':
                return '.wav'
            elif header[:4] == b'\x1aE\xdf\xa3':
                return '.webm'
        except Exception as e:
            logger.error(f'格式检测失败: {e}')
        return None

    def clear_cache(self):
        """清理缓存"""
        for file in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, file)
            try:
                os.remove(file_path)
            except Exception:
                pass
        self.cache = {}
        self._save_cache()

    def get_cache_size(self) -> int:
        """获取缓存大小（字节）"""
        total_size = 0
        for file in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, file)
            try:
                total_size += os.path.getsize(file_path)
            except Exception:
                pass
        return total_size

    def get_cache_count(self) -> int:
        """获取缓存文件数量"""
        try:
            return len([f for f in os.listdir(self.cache_dir) if os.path.isfile(os.path.join(self.cache_dir, f))])
        except Exception:
            return 0
