"""Native Kodi adaptation of Vette1123/movies-streaming-platform (MIT).

Catalog metadata is separate from playback: only configured direct media URLs
are sent to Kodi. Browser embeds and private upstream resolvers are not included.
"""
import json
import re
import sys
from urllib.parse import urlencode, parse_qsl, urlsplit, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]
REELY = 'https://www.reely.space'
AGENT = 'ReelyKodi/0.2.0'


def fetch(url):
    request = Request(url, headers={'User-Agent': AGENT, 'Referer': REELY + '/'})
    with urlopen(request, timeout=20) as response:
        data = response.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError('Response exceeds the 8 MB limit.')
    return data.decode('utf-8-sig')


def tmdb(path, **params):
    key = ADDON.getSetting('tmdb_key').strip()
    if not key:
        parts = path.split('/')
        if path == 'search/multi':
            result = json.loads(fetch(REELY + '/api/search?' + urlencode({'query': params['query']})))
            # The website search API returns only its first page.
            result['total_pages'] = 1
            return result
        if len(parts) == 2 and parts[1] == 'popular':
            return json.loads(fetch(REELY + '/api/popular?' + urlencode({'mediaType': parts[0], 'page': params.get('page', 1)})))
        if len(parts) == 2 and parts[0] == 'tv':
            return json.loads(fetch(REELY + '/api/media/tv/' + parts[1]))['seriesDetails']
        if len(parts) == 4 and parts[0] == 'tv' and parts[2] == 'season':
            return json.loads(fetch(REELY + '/api/season-details?' + urlencode({'seasonId': parts[1], 'seasonNumber': parts[3]})))
        raise ValueError('Unsupported catalog request.')
    params['api_key'] = key
    return json.loads(fetch('https://api.themoviedb.org/3/' + path + '?' + urlencode(params)))


def reely_stream(p):
    """Use the live website's normal signed ticket/session/resolve flow."""
    kind = 'tv' if p.get('kind') == 'tv' else 'movie'
    target = {'type': kind, 'id': int(p['id']), 'title': p.get('title') or 'Kodi playback'}
    if kind == 'tv':
        target.update(season=int(p.get('s', 1)), episode=int(p.get('e', 1)))
    headers = {'User-Agent': AGENT, 'Referer': REELY + '/', 'Content-Type': 'application/json'}
    def request(url, body=None):
        return urlopen(Request(url, data=body, headers=headers), timeout=40)
    try:
        with request(REELY + '/api/pro/ticket', json.dumps(target).encode('utf-8')) as response:
            ticket = json.load(response)
        if not ticket.get('success') or not ticket.get('url'):
            raise ValueError('Reely did not issue a playback ticket. Try again later.')
        with request(ticket['url']) as response:
            player_url = response.url
            response.read(1024)
        parsed = urlsplit(player_url)
        if parsed.scheme != 'https':
            raise ValueError('Reely returned an unsupported player URL.')
        query = dict(parse_qsl(parsed.query))
        if not query.get('t'):
            raise ValueError('Reely did not return a playback session token.')
        base = parsed.scheme + '://' + parsed.netloc
        args = {key: query[key] for key in ('type', 'id', 'season', 'episode', 't') if key in query}
        qs = urlencode(args)
        headers['Referer'] = player_url
        with request(base + '/api/session/start?' + qs, b'') as response:
            session = json.load(response)
        if not session.get('p'):
            raise ValueError('Reely could not start a playback session.')
        with request(base + '/api/stream/resolve?' + qs) as response:
            result = json.load(response)
        sources = result.get('sources') or []
        if not sources:
            raise ValueError('Reely has no native stream for this title right now. Browser-only fallback players cannot run in Kodi.')
        stream = sources[0].get('url', '')
        if urlsplit(stream).scheme not in ('http', 'https'):
            raise ValueError('Reely returned an unsupported stream URL.')
        # Preserve signed URLs unchanged and send the same page referrer as the web player.
        return stream + '|' + urlencode({'Referer': player_url, 'User-Agent': AGENT})
    except HTTPError as exc:
        if exc.code in (401, 402):
            raise ValueError('Reely now requires an account or supporter access. Kodi sign-in is not implemented.') from None
        if exc.code == 451:
            raise ValueError('Reely has disabled playback for this title.') from None
        if exc.code == 403:
            raise ValueError('Reely refused this playback request. Try later or use a configured direct stream.') from None
        raise


def route(**params):
    return BASE + '?' + urlencode(params)


def item(label, params, folder=True, data=None):
    li = xbmcgui.ListItem(label=label)
    if data:
        info = li.getVideoInfoTag()
        info.setTitle(label)
        info.setPlot(data.get('overview') or '')
        date = data.get('release_date') or data.get('first_air_date') or ''
        if date[:4].isdigit():
            info.setYear(int(date[:4]))
        art = {}
        if data.get('poster_path'):
            art['poster'] = 'https://image.tmdb.org/t/p/w500' + data['poster_path']
        if data.get('backdrop_path'):
            art['fanart'] = 'https://image.tmdb.org/t/p/w1280' + data['backdrop_path']
        li.setArt(art)
    if not folder and params.get('action') == 'play':
        li.setProperty('IsPlayable', 'true')
    xbmcplugin.addDirectoryItem(HANDLE, route(**params), li, isFolder=folder)


def parse_playlist(text, source):
    """Parse extended M3U; resolve HTTP-relative entries and local paths."""
    entries = []
    title = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('#EXTINF:'):
            title = line.partition(',')[2].strip() or 'Untitled stream'
        elif line and not line.startswith('#'):
            if urlsplit(source).scheme in ('http', 'https'):
                url = urljoin(source, line)
            elif not urlsplit(line).scheme and not line.startswith('/'):
                url = source.rsplit('/', 1)[0] + '/' + line
            else:
                url = line
            entries.append((title or line.rsplit('/', 1)[-1], url))
            title = None
    return entries


def expand_template(template, params):
    for token in ('id', 's', 'e'):
        value = str(params.get(token, '1'))
        if not value.isdigit():
            raise ValueError('Invalid title or episode identifier.')
        template = template.replace('{' + token + '}', value)
    if '{' in template or '}' in template:
        raise ValueError('Unsupported URL template token. Use {id}, {s}, {e}.')
    if urlsplit(template).scheme not in ('http', 'https'):
        raise ValueError('Stream templates must use HTTP or HTTPS.')
    return template


def home():
    item('Movies', {'action': 'browse', 'kind': 'movie'})
    item('TV shows', {'action': 'browse', 'kind': 'tv'})
    item('Search movies and TV', {'action': 'search'})
    item('My M3U playlist', {'action': 'playlist'})
    item('Open a direct video URL', {'action': 'direct'}, folder=False)
    item('Playback test — Sintel trailer', {
        'action': 'play', 'url': 'https://media.w3.org/2010/05/sintel/trailer.mp4',
        'title': 'Sintel trailer — playback test'}, folder=False)
    item('Settings', {'action': 'settings'}, folder=False)
    item('About playback setup', {'action': 'about'}, folder=False)
    xbmcplugin.endOfDirectory(HANDLE)


def browse(p):
    kind = p.get('kind', 'movie')
    page = int(p.get('page', '1'))
    search = p.get('query')
    result = tmdb('search/multi' if search else kind + '/popular', page=page, **({'query': search} if search else {}))
    xbmcplugin.setContent(HANDLE, 'videos' if search else ('movies' if kind == 'movie' else 'tvshows'))
    for row in result.get('results', []):
        row_kind = row.get('media_type', kind)
        if row_kind not in ('movie', 'tv'):
            continue
        label = row.get('title') or row.get('name') or 'Untitled'
        item(label, {'action': 'play' if row_kind == 'movie' else 'seasons', 'kind': row_kind,
                     'id': row['id'], 'title': label}, folder=row_kind == 'tv', data=row)
    if page < min(result.get('total_pages', 1), 500):
        item('Next page', {'action': 'browse', 'kind': kind, 'page': page + 1, **({'query': search} if search else {})})
    xbmcplugin.endOfDirectory(HANDLE)


def seasons(p):
    result = tmdb('tv/' + str(int(p['id'])))
    xbmcplugin.setContent(HANDLE, 'seasons')
    for season in result.get('seasons', []):
        item(season['name'], dict(action='episodes', id=p['id'], s=season['season_number'], title=p.get('title', '')), data=season)
    xbmcplugin.endOfDirectory(HANDLE)


def episodes(p):
    result = tmdb('tv/{}/season/{}'.format(int(p['id']), int(p['s'])))
    xbmcplugin.setContent(HANDLE, 'episodes')
    for episode in result.get('episodes', []):
        name = '{}. {}'.format(episode['episode_number'], episode['name'])
        item(name, dict(action='play', kind='tv', id=p['id'], s=p['s'], e=episode['episode_number'],
                        title=p.get('title', '') + ' — ' + name), folder=False, data=episode)
    xbmcplugin.endOfDirectory(HANDLE)


def playlist():
    source = ADDON.getSetting('playlist').strip()
    if not source:
        raise ValueError('Enter your M3U URL or local path in Settings first.')
    if urlsplit(source).scheme in ('http', 'https'):
        content = fetch(source)
    else:
        f = xbmcvfs.File(source)
        try:
            content = f.read()
        finally:
            f.close()
    # HLS playlists are streams, not directories of their media segments.
    if '#EXT-X-' in content:
        item('Play HLS stream', dict(action='play', url=source), folder=False)
    else:
        for label, url in parse_playlist(content, source):
            item(label, dict(action='play', url=url, title=label), folder=False)
    xbmcplugin.endOfDirectory(HANDLE)


def playback(p):
    url = p.get('url', '').strip()
    if not url:
        template = ADDON.getSetting('tv_template' if p.get('kind') == 'tv' else 'movie_template').strip()
        if not template:
            if ADDON.getSetting('use_reely') == 'false':
                raise ValueError('No stream source configured. Enable Reely website playback or set a direct-stream template.')
            url = reely_stream(p)
        else:
            url = expand_template(template, p)
    if urlsplit(url.split('|', 1)[0]).scheme not in ('http', 'https', 'smb', 'nfs', 'file', ''):
        raise ValueError('Unsupported playback URL scheme.')
    li = xbmcgui.ListItem(label=p.get('title', ''), path=url)
    li.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def main():
    p = dict(parse_qsl(sys.argv[2].lstrip('?')))
    action = p.get('action', 'home')
    try:
        if action == 'home':
            home()
        elif action == 'browse':
            browse(p)
        elif action == 'search':
            query = xbmcgui.Dialog().input('Search movies and TV')
            if query.strip():
                browse(dict(query=query.strip()))
            else:
                xbmcplugin.endOfDirectory(HANDLE)
        elif action == 'seasons':
            seasons(p)
        elif action == 'episodes':
            episodes(p)
        elif action == 'playlist':
            playlist()
        elif action == 'play':
            playback(p)
        elif action == 'direct':
            url = xbmcgui.Dialog().input('Direct video URL (MP4 or HLS, not a web page)')
            if url.strip():
                xbmc.Player().play(route(action='play', url=url.strip()))
        elif action == 'settings':
            ADDON.openSettings()
        elif action == 'refresh_repository':
            xbmc.executebuiltin('UpdateLocalAddons')
            xbmc.executebuiltin('UpdateAddonRepos')
            xbmcplugin.endOfDirectory(HANDLE)
        elif action == 'about':
            xbmcgui.Dialog().ok('Reely for Kodi', 'Browses the Reely website and requests native streams through its live playback service. Availability depends on Reely. Sign-in and browser-only fallback players are not supported. Direct URL templates and M3U playlists are also supported.')
        else:
            raise ValueError('Unknown action.')
    except Exception as exc:
        # Avoid logging signed URLs or API credentials from network exceptions.
        message = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else 'Unable to load this source. Check your network, credentials and source settings.'
        xbmc.log('Reely: ' + type(exc).__name__, xbmc.LOGERROR)
        xbmcgui.Dialog().ok('Reely', message)
        if action == 'play':
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        else:
            xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


if __name__ == '__main__':
    main()
