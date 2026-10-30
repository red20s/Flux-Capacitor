import importlib.util
import sys
import types
import unittest
import io
import json
from unittest.mock import MagicMock, patch

for name in ('xbmc', 'xbmcaddon', 'xbmcgui', 'xbmcplugin', 'xbmcvfs'):
    sys.modules[name] = MagicMock()
sys.argv = ['plugin://plugin.video.reely/', '1', '']
spec = importlib.util.spec_from_file_location('reely', str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'plugin.video.reely/addon.py'))
reely = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reely)

class Tests(unittest.TestCase):
    def test_playlist_names_and_relative_urls(self):
        entries = reely.parse_playlist('#EXTM3U\n#EXTINF:-1,Movie\nvideo.mp4\n# comment\nhttps://cdn.test/two.m3u8', 'https://cdn.test/list/index.m3u')
        self.assertEqual(entries, [('Movie', 'https://cdn.test/list/video.mp4'), ('two.m3u8', 'https://cdn.test/two.m3u8')])

    def test_episode_template(self):
        self.assertEqual(reely.expand_template('https://cdn.test/{id}/{s}/{e}.m3u8', dict(id='123', s='2', e='4')), 'https://cdn.test/123/2/4.m3u8')

    def test_bad_identifier_rejected(self):
        with self.assertRaises(ValueError):
            reely.expand_template('https://cdn.test/{id}', dict(id='../secret'))

    def test_missing_stream_does_not_report_success(self):
        reely.ADDON.getSetting.side_effect = lambda key: 'false' if key == 'use_reely' else ''
        reely.xbmcplugin.reset_mock()
        with self.assertRaises(ValueError):
            reely.playback(dict(kind='movie', id='1'))
        reely.xbmcplugin.setResolvedUrl.assert_not_called()
        reely.ADDON.getSetting.side_effect = None

    def test_native_playback_resolves(self):
        reely.xbmcplugin.reset_mock()
        reely.playback(dict(url='https://cdn.test/a.mp4', title='Test'))
        args = reely.xbmcplugin.setResolvedUrl.call_args.args
        self.assertEqual(args[:2], (1, True))

    def test_home_complete(self):
        reely.xbmcplugin.reset_mock()
        reely.home()
        self.assertEqual(reely.xbmcplugin.addDirectoryItem.call_count, 8)
        reely.xbmcplugin.endOfDirectory.assert_called_once_with(1)

    def test_reely_ticket_session_and_resolve(self):
        responses = []
        for value in ({'success': True, 'url': 'https://player.test/entry'}, {}, {'p':'session'}, {'sources':[{'url':'https://cdn.test/video.m3u8?sig=abc'}]}):
            response = io.BytesIO(json.dumps(value).encode())
            response.url = 'https://player.test/play?type=movie&id=45745&t=signed-token'
            responses.append(response)
        with patch.object(reely, 'urlopen', side_effect=responses) as fetch:
            result = reely.reely_stream(dict(kind='movie',id='45745',title='Sintel'))
        self.assertTrue(result.startswith('https://cdn.test/video.m3u8?sig=abc|'))
        self.assertEqual(fetch.call_count, 4)
        self.assertEqual(json.loads(fetch.call_args_list[0].args[0].data)['id'], 45745)

    def test_reely_respects_account_gate(self):
        error = reely.HTTPError('https://example.test', 402, 'Payment Required', {}, None)
        with patch.object(reely, 'urlopen', side_effect=error):
            with self.assertRaisesRegex(ValueError, 'supporter access'):
                reely.reely_stream(dict(kind='movie',id='45745',title='Sintel'))

    def test_reely_catalog_without_key(self):
        reely.ADDON.getSetting.return_value = ''
        with patch.object(reely, 'fetch', return_value='{"results": [], "total_pages": 50}') as fetch:
            result = reely.tmdb('search/multi', query='Sintel', page=1)
        self.assertEqual(result['total_pages'], 1)
        self.assertIn('/api/search?', fetch.call_args.args[0])

unittest.main(argv=['test_addon'])
