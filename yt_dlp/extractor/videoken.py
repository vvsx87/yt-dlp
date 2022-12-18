import base64
import itertools
import time
import urllib.parse

from .common import InfoExtractor
from ..utils import (
    int_or_none,
    traverse_obj,
    update_url_query,
    url_or_none,
)


class VideoKenBaseIE(InfoExtractor):
    _BASE_URL_RE = r'''(?x)https?://
        (?P<host>videos\.(?:
            icts\.res\.in|
            cncf\.io|
            neurips\.cc))/'''
    _ORGANIZATIONS = {
        'videos.icts.res.in': 'icts',
        'videos.cncf.io': 'cncf',
        'videos.neurips.cc': 'neurips',
    }

    def _get_org_id_and_api_key(self, org, video_id):
        details = self._download_json(
            f'https://analytics.videoken.com/api/videolake/{org}/details', video_id,
            note='Downloading organization ID and API key', headers={
                'Accept': 'application/json',
            })
        return details['id'], details['apikey']

    def _create_slideslive_url(self, video_url, video_id, referer):
        if not video_url and not video_id:
            return
        elif not video_url or 'embed/sign-in' in video_url:
            video_url = f'https://slideslive.com/embed/{video_id.lstrip("slideslive-")}'
        if url_or_none(referer):
            return update_url_query(video_url, {
                'embed_parent_url': referer,
                'embed_container_origin': f'https://{urllib.parse.urlparse(referer).netloc}',
            })
        return video_url

    def _extract_videos(self, videos, url):
        for video in traverse_obj(videos, ('videos', ...)):
            video_id = video.get('youtube_id')
            if not video_id:
                continue
            ie_key = None
            if video.get('type') == 'youtube':
                video_url = video_id
                ie_key = 'Youtube'
            else:
                video_url = video.get('embed_url')
                if urllib.parse.urlparse(video_url).netloc == 'slideslive.com':
                    ie_key = 'SlidesLive'
                    video_url = self._create_slideslive_url(video_url, video_id, url)
            if not video_url:
                continue
            yield self.url_result(video_url, ie_key, video_id)


class VideoKenIE(VideoKenBaseIE):
    _VALID_URL = VideoKenBaseIE._BASE_URL_RE + r'(?:(?:topic|category)/[^/#?]+/)?video/(?P<id>[\w_-]+)'
    _TESTS = [{
        # neurips -> videoken -> slideslive
        'url': 'https://videos.neurips.cc/video/slideslive-38922815',
        'info_dict': {
            'id': '38922815',
            'ext': 'mp4',
            'title': 'Efficient Processing of Deep Neural Network: from Algorithms to Hardware Architectures',
            'timestamp': 1630939331,
            'upload_date': '20210906',
            'thumbnail': r're:^https?://.*\.(?:jpg|png)',
            'thumbnails': 'count:330',
            'chapters': 'count:329',
        },
        'params': {
            'skip_download': 'm3u8',
        },
    }, {
        # neurips -> videoken -> slideslive -> youtube
        'url': 'https://videos.neurips.cc/topic/machine%20learning/video/slideslive-38923348',
        'info_dict': {
            'id': '2Xa_dt78rJE',
            'ext': 'mp4',
            'display_id': '38923348',
            'title': 'Machine Education',
            'description': 'Watch full version of this video at https://slideslive.com/38923348.',
            'channel': 'SlidesLive Videos - G2',
            'channel_id': 'UCOExahQQ588Da8Nft_Ltb9w',
            'channel_url': 'https://www.youtube.com/channel/UCOExahQQ588Da8Nft_Ltb9w',
            'uploader': 'SlidesLive Videos - G2',
            'uploader_id': 'UCOExahQQ588Da8Nft_Ltb9w',
            'uploader_url': 'http://www.youtube.com/channel/UCOExahQQ588Da8Nft_Ltb9w',
            'duration': 2504,
            'timestamp': 1618922125,
            'upload_date': '20200131',
            'age_limit': 0,
            'channel_follower_count': int,
            'view_count': int,
            'availability': 'unlisted',
            'live_status': 'not_live',
            'playable_in_embed': True,
            'categories': ['People & Blogs'],
            'tags': [],
            'thumbnail': r're:^https?://.*\.(?:jpg|webp)',
            'thumbnails': 'count:78',
            'chapters': 'count:77',
        },
        'params': {
            'skip_download': 'm3u8',
        },
    }, {
        # icts -> videoken -> youtube
        'url': 'https://videos.icts.res.in/topic/random%20variable/video/zysIsojYdvc',
        'info_dict': {
            'id': 'zysIsojYdvc',
            'ext': 'mp4',
            'title': 'Small-worlds, complex networks and random graphs (Lecture 3)  by Remco van der Hofstad',
            'description': 'md5:87433069d79719eeadc1962cc2ace00b',
            'channel': 'International Centre for Theoretical Sciences',
            'channel_id': 'UCO3xnVTHzB7l-nc8mABUJIQ',
            'channel_url': 'https://www.youtube.com/channel/UCO3xnVTHzB7l-nc8mABUJIQ',
            'uploader': 'International Centre for Theoretical Sciences',
            'uploader_id': 'ICTStalks',
            'uploader_url': 'http://www.youtube.com/user/ICTStalks',
            'duration': 3372,
            'upload_date': '20191004',
            'age_limit': 0,
            'live_status': 'not_live',
            'availability': 'public',
            'playable_in_embed': True,
            'channel_follower_count': int,
            'like_count': int,
            'view_count': int,
            'categories': ['Science & Technology'],
            'tags': [],
            'thumbnail': r're:^https?://.*\.(?:jpg|webp)',
            'thumbnails': 'count:42',
            'chapters': 'count:20',
        },
        'params': {
            'skip_download': 'm3u8',
        },
    }, {
        'url': 'https://videos.cncf.io/category/478/video/IL4nxbmUIX8',
        'only_matching': True,
    }, {
        'url': 'https://videos.cncf.io/topic/kubernetes/video/YAM2d7yTrrI',
        'only_matching': True,
    }, {
        'url': 'https://videos.icts.res.in/video/d7HuP_abpKU',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        hostname, video_id = self._match_valid_url(url).group('host', 'id')
        org_id, _ = self._get_org_id_and_api_key(self._ORGANIZATIONS[hostname], video_id)
        details = self._download_json(
            'https://analytics.videoken.com/api/embedded/videodetails/', video_id, query={
                'video': video_id,
                'org_id': org_id,
            }, headers={'Accept': 'application/json'}, note='Downloading API JSON')

        embed_type = details['type']
        ie_key = None
        if embed_type == 'youtube':
            embed_url = video_id
            ie_key = 'Youtube'
        else:
            embed_url = details['embed_url']
            if urllib.parse.urlparse(embed_url).netloc == 'slideslive.com':
                ie_key = 'SlidesLive'
                embed_url = self._create_slideslive_url(embed_url, video_id, url)

        return self.url_result(embed_url, ie_key, video_id)


class VideoKenPlayerIE(VideoKenBaseIE):
    _VALID_URL = r'https?://player\.videoken\.com/embed/slideslive-(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://player.videoken.com/embed/slideslive-38968434',
        'info_dict': {
            'id': '38968434',
            'ext': 'mp4',
            'title': 'Deep Learning with Label Differential Privacy',
            'timestamp': 1643377020,
            'upload_date': '20220128',
            'thumbnail': r're:^https?://.*\.(?:jpg|png)',
            'thumbnails': 'count:30',
            'chapters': 'count:29',
        },
        'params': {
            'skip_download': 'm3u8',
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        return self.url_result(
            self._create_slideslive_url(None, video_id, url), 'SlidesLive', video_id)


class VideoKenPlaylistIE(VideoKenBaseIE):
    _VALID_URL = VideoKenBaseIE._BASE_URL_RE + r'(?:category/\d+/)?playlist/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://videos.icts.res.in/category/1822/playlist/381',
        'playlist_mincount': 117,
        'info_dict': {
            'id': '381',
            'title': 'Cosmology - The Next Decade',
        },
    }]

    def _real_extract(self, url):
        hostname, playlist_id = self._match_valid_url(url).group('host', 'id')
        org_id, _ = self._get_org_id_and_api_key(self._ORGANIZATIONS[hostname], playlist_id)
        videos = self._download_json(
            f'https://analytics.videoken.com/api/videolake/{org_id}/playlistitems/{playlist_id}/',
            playlist_id, headers={'Accept': 'application/json'}, note='Downloading API JSON')
        playlist_title = videos.get('title') or playlist_id
        return self.playlist_result(self._extract_videos(videos, url), playlist_id, playlist_title)


class VideoKenCategoryIE(VideoKenBaseIE):
    _VALID_URL = VideoKenBaseIE._BASE_URL_RE + r'category/(?P<id>\d+)/?(?:$|[?#])'
    _TESTS = [{
        'url': 'https://videos.icts.res.in/category/1822/',
        'playlist_mincount': 60,
        'info_dict': {
            'id': '1822',
            'title': 'Programs',
        },
    }, {
        'url': 'https://videos.neurips.cc/category/350/',
        'playlist_mincount': 30,
        'info_dict': {
            'id': '350',
            'title': 'NeurIPS 2018',
        },
    }, {
        'url': 'https://videos.cncf.io/category/479/',
        'playlist_mincount': 100,
        'info_dict': {
            'id': '479',
            'title': 'KubeCon + CloudNativeCon Europe\'19',
        },
    }]

    def _get_category_page(self, category_id, org_id, page=1, note=None):
        return self._download_json(
            f'https://analytics.videoken.com/api/videolake/{org_id}/category_videos', category_id,
            fatal=False, note=note if note else f'Downloading category page {page}',
            query={
                'category_id': category_id,
                'page_number': page,
                'length': '12',
            }, headers={'Accept': 'application/json'}) or {}

    def _entries(self, category_id, org_id, url):
        for page in itertools.count(1):
            videos = self._get_category_page(category_id, org_id, page)
            is_last_page = videos.get('is_last_page')
            if is_last_page is None:
                break
            yield from self._extract_videos(videos, url)
            if is_last_page:
                break

    def _real_extract(self, url):
        hostname, category_id = self._match_valid_url(url).group('host', 'id')
        org_id, _ = self._get_org_id_and_api_key(self._ORGANIZATIONS[hostname], category_id)
        category = self._get_category_page(
            category_id, org_id, note='Downloading category info')['category_name']
        return self.playlist_result(
            self._entries(category_id, org_id, url), category_id, category)


class VideoKenTopicIE(VideoKenBaseIE):
    _VALID_URL = VideoKenBaseIE._BASE_URL_RE + r'topic/(?P<id>[^/#?]+)/?(?:$|[?#])'
    _TESTS = [{
        'url': 'https://videos.neurips.cc/topic/machine%20learning/',
        'playlist_mincount': 100,
        'info_dict': {
            'id': 'machine%20learning',
            'title': 'machine learning',
        },
    }, {
        'url': 'https://videos.icts.res.in/topic/gravitational%20waves/',
        'playlist_mincount': 77,
        'info_dict': {
            'id': 'gravitational%20waves',
            'title': 'gravitational waves'
        },
    }, {
        'url': 'https://videos.cncf.io/topic/prometheus/',
        'playlist_mincount': 134,
        'info_dict': {
            'id': 'prometheus',
            'title': 'prometheus',
        },
    }]

    def _get_topic_page(self, topic, org_id, search_id, api_key, page=1):
        return self._download_json(
            'https://es.videoken.com/api/v1.0/get_results', topic, fatal=False, query={
                'orgid': org_id,
                'size': '12',
                'query': topic,
                'page': page,
                'sort': 'upload_desc',
                'filter': 'all',
                'token': api_key,
                'is_topic': 'true',
                'category': '',
                'searchid': search_id,
            }, headers={'Accept': 'application/json'}, note=f'Downloading topic page {page}') or {}

    def _entries(self, topic, org_id, search_id, api_key, url):
        for page in itertools.count(1):
            videos = self._get_topic_page(topic, org_id, search_id, api_key, page)
            total_pages = int_or_none(videos.get('total_no_of_pages'))
            if not total_pages:
                break
            for video in traverse_obj(videos, ('results', ...)):
                video_id = video.get('videoid')
                if not video_id:
                    continue
                ie_key = None
                if video.get('source') == 'youtube':
                    video_url = video_id
                    ie_key = 'Youtube'
                else:
                    video_url = video.get('embeddableurl')
                    if urllib.parse.urlparse(video_url).netloc == 'slideslive.com':
                        ie_key = 'SlidesLive'
                        video_url = self._create_slideslive_url(video_url, video_id, url)
                if not video_url:
                    continue
                yield self.url_result(video_url, ie_key, video_id)
            if page == total_pages:
                break

    def _real_extract(self, url):
        hostname, topic_id = self._match_valid_url(url).group('host', 'id')
        topic = urllib.parse.unquote(topic_id)
        org_id, api_key = self._get_org_id_and_api_key(self._ORGANIZATIONS[hostname], topic)
        search_id = base64.b64encode(f':{topic}:{int(time.time())}:transient'.encode()).decode()
        return self.playlist_result(
            self._entries(topic, org_id, search_id, api_key, url), topic_id, topic)
