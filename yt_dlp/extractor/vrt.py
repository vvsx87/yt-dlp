import functools
import json
import urllib.parse
import urllib.request

from .common import InfoExtractor
from ..utils import (
    clean_html,
    extract_attributes,
    float_or_none,
    get_element_by_class,
    get_element_html_by_class,
    int_or_none,
    make_archive_id,
    merge_dicts,
    parse_age_limit,
    parse_iso8601,
    unified_strdate,
    str_or_none,
    strip_or_none,
    traverse_obj,
    url_or_none,
)


class VRTBaseIE(InfoExtractor):
    _GEO_BYPASS = False

    def _extract_formats_and_subtitles(self, data, video_id):
        if traverse_obj(data, 'drm'):
            self.report_drm(video_id)

        formats, subtitles = [], {}
        for target in traverse_obj(
            data, ('targetUrls', lambda _, v: url_or_none(v['url']) and v['type'])
        ):
            format_type = target['type'].upper()
            format_url = target['url']
            if format_type in ('HLS', 'HLS_AES'):
                fmts, subs = self._extract_m3u8_formats_and_subtitles(
                    format_url, video_id, 'mp4', m3u8_id=format_type, fatal=False
                )
                formats.extend(fmts)
                self._merge_subtitles(subs, target=subtitles)
            elif format_type == 'HDS':
                formats.extend(
                    self._extract_f4m_formats(
                        format_url, video_id, f4m_id=format_type, fatal=False
                    )
                )
            elif format_type == 'MPEG_DASH':
                fmts, subs = self._extract_mpd_formats_and_subtitles(
                    format_url, video_id, mpd_id=format_type, fatal=False
                )
                formats.extend(fmts)
                self._merge_subtitles(subs, target=subtitles)
            elif format_type == 'HSS':
                fmts, subs = self._extract_ism_formats_and_subtitles(
                    format_url, video_id, ism_id='mss', fatal=False
                )
                formats.extend(fmts)
                self._merge_subtitles(subs, target=subtitles)
            else:
                formats.append(
                    {
                        'format_id': format_type,
                        'url': format_url,
                    }
                )

        for sub in traverse_obj(
            data, ('subtitleUrls', lambda _, v: v['url'] and v['type'] == 'CLOSED')
        ):
            subtitles.setdefault('nl', []).append({'url': sub['url']})

        return formats, subtitles

    def _call_api(self, video_id, client='null', id_token=None, version='v2'):
        json_response = self._download_json(
            f'https://media-services-public.vrt.be/vualto-video-aggregator-web/rest/external/{version}/tokens',
            None,
            'Downloading player token',
            'Failed to download player token',
            headers={'Content-Type': 'application/json'},
            data=json.dumps(
                {
                    'identityToken': id_token
                    or self._get_cookies('https://www.vrt.be')
                    .get('vrtnu-site_profile_vt')
                    .value
                }
            ).encode(),
        )
        player_token = json_response['vrtPlayerToken']

        return self._download_json(
            f'https://media-services-public.vrt.be/vualto-video-aggregator-web/rest/external/{version}/videos/{video_id}',
            video_id,
            'Downloading API JSON',
            'Failed to download API JSON',
            query={
                'vrtPlayerToken': player_token,
                'client': client,
            },
        )


class VRTLoginIE(VRTBaseIE):
    _NETRC_MACHINE = 'vrtnu'
    _authenticated = False

    def _perform_login(self, username, password):
        self._request_webpage(
            'https://www.vrt.be/vrtnu/sso/login',
            None,
            note='Getting session cookies',
            errnote='Failed to get session cookies',
        )

        self._download_json(
            'https://login.vrt.be/perform_login',
            None,
            data=json.dumps(
                {'loginID': username, 'password': password, 'clientId': 'vrtnu-site'}
            ).encode(),
            headers={
                'Content-Type': 'application/json',
                'Oidcxsrf': self._get_cookies('https://login.vrt.be')
                .get('OIDCXSRF')
                .value,
            },
            note='Logging in',
            errnote='Login failed',
        )
        self._authenticated = True
        return


class VRTIE(VRTLoginIE):
    IE_DESC = 'VRT NWS, Flanders News, Flandern Info and Sporza'
    _VALID_URL = r'https?://(?:www\.)?(?P<site>vrt\.be/vrtnws|sporza\.be)/[a-z]{2}/\d{4}/\d{2}/\d{2}/(?P<id>[^/?&#]+)'
    _TESTS = [
        {
            'url': 'https://www.vrt.be/vrtnws/nl/2019/05/15/beelden-van-binnenkant-notre-dame-een-maand-na-de-brand/',
            'info_dict': {
                'id': 'pbs-pub-7855fc7b-1448-49bc-b073-316cb60caa71$vid-2ca50305-c38a-4762-9890-65cbd098b7bd',
                'ext': 'mp4',
                'title': 'Beelden van binnenkant Notre-Dame, één maand na de brand',
                'description': 'md5:6fd85f999b2d1841aa5568f4bf02c3ff',
                'duration': 31.2,
                'thumbnail': 'https://images.vrt.be/orig/2019/05/15/2d914d61-7710-11e9-abcc-02b7b76bf47f.jpg',
            },
            'params': {'skip_download': 'm3u8'},
        },
        {
            'url': 'https://sporza.be/nl/2019/05/15/de-belgian-cats-zijn-klaar-voor-het-ek/',
            'info_dict': {
                'id': 'pbs-pub-e1d6e4ec-cbf4-451e-9e87-d835bb65cd28$vid-2ad45eb6-9bc8-40d4-ad72-5f25c0f59d75',
                'ext': 'mp4',
                'title': 'De Belgian Cats zijn klaar voor het EK',
                'description': 'Video: De Belgian Cats zijn klaar voor het EK mét Ann Wauters | basketbal, sport in het journaal',
                'duration': 115.17,
                'thumbnail': 'https://images.vrt.be/orig/2019/05/15/11c0dba3-770e-11e9-abcc-02b7b76bf47f.jpg',
            },
            'params': {'skip_download': 'm3u8'},
        },
    ]
    _APIKEY = '3_0Z2HujMtiWq_pkAjgnS2Md2E11a1AwZjYiBETtwNE-EoEHDINgtnvcAOpNgmrVGy'
    _CONTEXT_ID = 'R3595707040'
    _REST_API_BASE_TOKEN = 'https://media-services-public.vrt.be/vualto-video-aggregator-web/rest/external/v2'
    _REST_API_BASE_VIDEO = 'https://media-services-public.vrt.be/media-aggregator/v2'
    _HLS_ENTRY_PROTOCOLS_MAP = {
        'HLS': 'm3u8_native',
        'HLS_AES': 'm3u8_native',
    }

    def _real_extract(self, url):
        site, display_id = self._match_valid_url(url).groups()
        webpage = self._download_webpage(url, display_id)
        attrs = extract_attributes(get_element_html_by_class('vrtvideo', webpage) or '')

        asset_id = attrs.get('data-video-id') or attrs['data-videoid']
        publication_id = traverse_obj(
            attrs, 'data-publication-id', 'data-publicationid'
        )
        if publication_id:
            asset_id = f'{publication_id}${asset_id}'
        client = (
            traverse_obj(attrs, 'data-client-code', 'data-client')
            or self._CLIENT_MAP[site]
        )

        data = self._call_api(asset_id, client)
        formats, subtitles = self._extract_formats_and_subtitles(data, asset_id)

        description = self._html_search_meta(
            ['og:description', 'twitter:description', 'description'], webpage
        )
        if description == '…':
            description = None

        return {
            'id': asset_id,
            'formats': formats,
            'subtitles': subtitles,
            'description': description,
            'thumbnail': url_or_none(attrs.get('data-posterimage')),
            'duration': float_or_none(attrs.get('data-duration'), 1000),
            '_old_archive_ids': [make_archive_id('Canvas', asset_id)],
            **traverse_obj(
                data,
                {
                    'title': ('title', {str}),
                    'description': ('shortDescription', {str}),
                    'duration': (
                        'duration',
                        {functools.partial(float_or_none, scale=1000)},
                    ),
                    'thumbnail': ('posterImageUrl', {url_or_none}),
                },
            ),
        }


class VrtNUIE(VRTLoginIE):
    IE_DESC = 'VRT MAX'
    _VALID_URL = (
        r'https?://(?:www\.)?vrt\.be/(vrtmax|vrtnu)/a-z/(?:[^/]+/){2}(?P<id>[^/?#&]+)'
    )
    _TESTS = [
        {
            'url': 'https://www.vrt.be/vrtmax/a-z/pano/trailer/pano-trailer-najaar-2023/',
            'info_dict': {
                'title': 'Pano - Nieuwe afleveringen vanaf 15 november - Trailer | VRT MAX',
                'description': 'Duidingsmagazine met indringende reportages over de grote thema\'s van deze tijd. Een gedreven team van reporters diept de beste nieuwsverhalen uit en zoekt het antwoord op actuele vragen. Bekijk de trailer met VRT MAX via de site of app.',
                'timestamp': 1699246800,
                'release_timestamp': 1699246800,
                'release_date': '20231106',
                'upload_date': '20231106',
                'series': 'Pano',
                'season': 'Trailer',
                'season_number': 2023,
                'season_id': '/vrtnu/a-z/pano/trailer/#tvseason',
                'episode_id': '3226122918145',
                'id': 'pbs-pub-5260ad6d-372c-46d3-a542-0e781fd5831a$vid-75fdb750-82f5-4157-8ea9-4485f303f20b',
                'channel': 'VRT',
                'duration': 37.16,
                'thumbnail': 'https://images.vrt.be/orig/2023/11/03/f570eb9b-7a4e-11ee-91d7-02b7b76bf47f.jpg',
                'ext': 'mp4',
            },
        },
        {
            'url': 'https://www.vrt.be/vrtnu/a-z/factcheckers/trailer/factcheckers-trailer-s4/',
            'info_dict': {
                'title': 'Factcheckers - Nieuwe afleveringen vanaf 15 november - Trailer | VRT MAX',
                'season_number': 2023,
                'description': 'Infotainmentprogramma waarin Thomas Vanderveken, Jan Van Looveren en Britt Van Marsenille checken wat er nu eigenlijk klopt van de tsunami aan berichten, beweringen en weetjes die we dagelijks over ons heen krijgen. Bekijk de trailer met VRT MAX via de site of app.',
                'timestamp': 1699160400,
                'release_timestamp': 1699160400,
                'release_date': '20231105',
                'upload_date': '20231105',
                'series': 'Factcheckers',
                'episode': '0',
                'episode_number': 0,
                'season': 'Trailer',
                'season_id': '/vrtnu/a-z/factcheckers/trailer/#tvseason',
                'episode_id': '3179360900145',
                'id': 'pbs-pub-aa9397e9-ec2b-45f9-9148-7ce71b690b45$vid-04c67438-4866-4f5c-8978-51d173c0074b',
                'channel': 'VRT',
                'duration': 33.08,
                'thumbnail': 'https://images.vrt.be/orig/2023/11/07/37d244f0-7d8a-11ee-91d7-02b7b76bf47f.jpg',
                'ext': 'mp4',
            },
        },
    ]

    _NETRC_MACHINE = 'vrtnu'

    _VIDEOPAGE_QUERY = 'query VideoPage($pageId: ID!) {\n page(id: $pageId) {\n  ... on EpisodePage {\n   id\n   title\n   seo {\n    ...seoFragment\n    __typename\n   }\n   ldjson\n   episode {\n    onTimeRaw\n    ageRaw\n    name\n    episodeNumberRaw\n    program {\n     title\n     __typename\n    }\n    watchAction {\n     streamId\n     __typename\n    }\n    __typename\n   }\n   __typename\n  }\n  __typename\n }\n}\nfragment seoFragment on SeoProperties {\n __typename\n title\n description\n}'

    def _real_extract(self, url):
        display_id = self._match_id(url)
        parsed_url = urllib.parse.urlparse(url)

        self._request_webpage(
            'https://www.vrt.be/vrtnu/sso/login',
            None,
            note='Getting tokens',
            errnote='Failed to get tokens',
        )

        metadata = self._download_json(
            'https://www.vrt.be/vrtnu-api/graphql/v1',
            display_id,
            'Downloading asset JSON',
            'Unable to download asset JSON',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self._get_cookies("https://www.vrt.be").get("vrtnu-site_profile_at").value}',
            },
            data=json.dumps(
                {
                    'operationName': 'VideoPage',
                    'query': self._VIDEOPAGE_QUERY,
                    'variables': {
                        'pageId': f'{parsed_url.path.rstrip("/")}.model.json'
                    },
                }
            ).encode(),
        )['data']['page']

        video_id = metadata['episode']['watchAction']['streamId']
        try:
            ld_json = json.loads(metadata['ldjson'][1])
        except Exception:
            ld_json = {}

        streaming_info = self._call_api(video_id, client='vrtnu-web@PROD')
        formats, subtitles = self._extract_formats_and_subtitles(
            streaming_info, video_id
        )

        return {
            **traverse_obj(
                metadata,
                {
                    'title': ('seo', 'title', {str_or_none}),
                    'season_number': (
                        'episode',
                        'onTimeRaw',
                        {lambda x: x[:4]},
                        {int_or_none},
                    ),
                    'description': ('seo', 'description', {str_or_none}),
                    'timestamp': ('episode', 'onTimeRaw', {parse_iso8601}),
                    'release_timestamp': ('episode', 'onTimeRaw', {parse_iso8601}),
                    'release_date': ('episode', 'onTimeRaw', {unified_strdate}),
                    'upload_date': ('episode', 'onTimeRaw', {unified_strdate}),
                    'series': ('episode', 'program', 'title'),
                    'episode': ('episode', 'episodeNumberRaw', {str_or_none}),
                    'episode_number': ('episode', 'episodeNumberRaw', {int_or_none}),
                    'age_limit': ('episode', 'ageRaw', {parse_age_limit}),
                    'display_id': ('episode', 'name', {parse_age_limit}),
                },
            ),
            **traverse_obj(
                ld_json,
                {
                    'season': ('partOfSeason', 'name'),
                    'season_id': ('partOfSeason', '@id'),
                    'episode_id': ('@id', {str_or_none}),
                },
            ),
            'id': video_id,
            'channel': 'VRT',
            'formats': formats,
            'duration': float_or_none(streaming_info.get('duration'), 1000),
            'thumbnail': url_or_none(streaming_info.get('posterImageUrl')),
            'subtitles': subtitles,
            '_old_archive_ids': [make_archive_id('Canvas', video_id)],
        }


class KetnetIE(VRTBaseIE):
    _VALID_URL = r'https?://(?:www\.)?ketnet\.be/(?P<id>(?:[^/]+/)*[^/?#&]+)'
    _TESTS = [
        {
            'url': 'https://www.ketnet.be/kijken/m/meisjes/6/meisjes-s6a5',
            'info_dict': {
                'id': 'pbs-pub-39f8351c-a0a0-43e6-8394-205d597d6162$vid-5e306921-a9aa-4fa9-9f39-5b82c8f1028e',
                'ext': 'mp4',
                'title': 'Meisjes',
                'episode': 'Reeks 6: Week 5',
                'season': 'Reeks 6',
                'series': 'Meisjes',
                'timestamp': 1685251800,
                'upload_date': '20230528',
            },
            'params': {'skip_download': 'm3u8'},
        }
    ]

    def _real_extract(self, url):
        display_id = self._match_id(url)

        video = self._download_json(
            'https://senior-bff.ketnet.be/graphql',
            display_id,
            query={
                'query': '''{
  video(id: "content/ketnet/nl/%s.model.json") {
    description
    episodeNr
    imageUrl
    mediaReference
    programTitle
    publicationDate
    seasonTitle
    subtitleVideodetail
    titleVideodetail
  }
}'''
                % display_id,
            },
        )['data']['video']

        video_id = urllib.parse.unquote(video['mediaReference'])
        data = self._call_api(video_id, 'ketnet@PROD', version='v1')
        formats, subtitles = self._extract_formats_and_subtitles(data, video_id)

        return {
            'id': video_id,
            'formats': formats,
            'subtitles': subtitles,
            '_old_archive_ids': [make_archive_id('Canvas', video_id)],
            **traverse_obj(
                video,
                {
                    'title': ('titleVideodetail', {str}),
                    'description': ('description', {str}),
                    'thumbnail': ('thumbnail', {url_or_none}),
                    'timestamp': ('publicationDate', {parse_iso8601}),
                    'series': ('programTitle', {str}),
                    'season': ('seasonTitle', {str}),
                    'episode': ('subtitleVideodetail', {str}),
                    'episode_number': ('episodeNr', {int_or_none}),
                },
            ),
        }


class DagelijkseKostIE(VRTBaseIE):
    IE_DESC = 'dagelijksekost.een.be'
    _VALID_URL = r'https?://dagelijksekost\.een\.be/gerechten/(?P<id>[^/?#&]+)'
    _TESTS = [
        {
            'url': 'https://dagelijksekost.een.be/gerechten/hachis-parmentier-met-witloof',
            'info_dict': {
                'id': 'md-ast-27a4d1ff-7d7b-425e-b84f-a4d227f592fa',
                'ext': 'mp4',
                'title': 'Hachis parmentier met witloof',
                'description': 'md5:9960478392d87f63567b5b117688cdc5',
                'display_id': 'hachis-parmentier-met-witloof',
            },
            'params': {'skip_download': 'm3u8'},
        }
    ]

    def _real_extract(self, url):
        display_id = self._match_id(url)
        webpage = self._download_webpage(url, display_id)
        video_id = self._html_search_regex(
            r'data-url=(["\'])(?P<id>(?:(?!\1).)+)\1', webpage, 'video id', group='id'
        )

        data = self._call_api(video_id, 'dako@prod', version='v1')
        formats, subtitles = self._extract_formats_and_subtitles(data, video_id)

        return {
            'id': video_id,
            'formats': formats,
            'subtitles': subtitles,
            'display_id': display_id,
            'title': strip_or_none(
                get_element_by_class('dish-metadata__title', webpage)
                or self._html_search_meta('twitter:title', webpage)
            ),
            'description': clean_html(get_element_by_class('dish-description', webpage))
            or self._html_search_meta(
                ['description', 'twitter:description', 'og:description'], webpage
            ),
            '_old_archive_ids': [make_archive_id('Canvas', video_id)],
        }


class Radio1BeIE(VRTBaseIE):
    _VALID_URL = r'https?://radio1\.be/(?:lees|luister/select)/(?P<id>[\w/-]+)'
    _TESTS = [{
        'url': 'https://radio1.be/luister/select/de-ochtend/komt-n-va-volgend-jaar-op-in-wallonie',
        'info_dict': {
            'id': 'eb6c22e9-544f-44f4-af39-cf8cccd29e22',
            'title': 'Komt N-VA volgend jaar op in Wallonië?',
            'display_id': 'de-ochtend/komt-n-va-volgend-jaar-op-in-wallonie',
            'description': 'md5:b374ea1c9302f38362df9dea1931468e',
            'thumbnail': r're:https?://cds\.vrt\.radio/[^/#\?&]+'
        },
        'playlist_mincount': 1
    }, {
        'url': 'https://radio1.be/lees/europese-unie-wil-onmiddellijke-humanitaire-pauze-en-duurzaam-staakt-het-vuren-in-gaza?view=web',
        'info_dict': {
            'id': '5d47f102-dbdb-4fa0-832b-26c1870311f2',
            'title': 'Europese Unie wil "onmiddellijke humanitaire pauze" en "duurzaam staakt-het-vuren" in Gaza',
            'description': 'md5:1aad1fae7d39edeffde5d3e67d276b64',
            'thumbnail': r're:https?://cds\.vrt\.radio/[^/#\?&]+',
            'display_id': 'europese-unie-wil-onmiddellijke-humanitaire-pauze-en-duurzaam-staakt-het-vuren-in-gaza'
        },
        'playlist_mincount': 1
    }]

    def _extract_video_entries(self, next_js_data, display_id):
        video_data = traverse_obj(
            next_js_data, ((None, ('paragraphs', ...)), {lambda x: x if x['mediaReference'] else None}))
        for data in video_data:
            media_reference = data['mediaReference']
            formats, subtitles = self._extract_formats_and_subtitles(
                self._call_api(media_reference), display_id)

            yield {
                'id': media_reference,
                'formats': formats,
                'subtitles': subtitles,
                **traverse_obj(data, {
                    'title': ('title', {str}),
                    'description': ('body', {clean_html})
                }),
            }

    def _real_extract(self, url):
        display_id = self._match_id(url)
        webpage = self._download_webpage(url, display_id)
        next_js_data = self._search_nextjs_data(webpage, display_id)['props']['pageProps']['item']

        return self.playlist_result(
            self._extract_video_entries(next_js_data, display_id), **merge_dicts(traverse_obj(
                next_js_data, ({
                    'id': ('id', {str}),
                    'title': ('title', {str}),
                    'description': (('description', 'content'), {clean_html}),
                }), get_all=False), {
                    'display_id': display_id,
                    'title': self._html_search_meta(['name', 'og:title', 'twitter:title'], webpage),
                    'description': self._html_search_meta(['description', 'og:description', 'twitter:description'], webpage),
                    'thumbnail': self._html_search_meta(['og:image', 'twitter:image'], webpage),
            }))
