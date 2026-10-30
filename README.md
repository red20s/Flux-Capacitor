# Reely for Kodi — Flux Capacitor

An unofficial Kodi adaptation of [Vette1123/movies-streaming-platform](https://github.com/Vette1123/movies-streaming-platform). Browse movies and TV from [Reely](https://www.reely.space/) and play available native streams inside Kodi.

## Install

Download [repository.reely-0.2.0.zip](dist/repository.reely-0.2.0.zip), then in Kodi:

1. Enable **Settings → System → Add-ons → Unknown sources** if needed.
2. Choose **Add-ons → Install from zip file** and select the downloaded ZIP.
3. Open **Install from repository → Reely Local Repository → Video add-ons → Reely for Kodi**.

Alternatively, install [plugin.video.reely-0.2.0.zip](dist/plugin.video.reely-0.2.0.zip) directly. Restart Kodi if the newly installed local repository initially appears empty.

The bundled repository is an offline snapshot. Its small Kodi service serves the packaged index and ZIP only on `127.0.0.1:18764`. A PC is not required. Updates require installing a newer package; this is not an automatic GitHub update feed.

## Playback and settings

- Movies, TV, seasons, episodes and search use Reely by default; no personal TMDB key is required.
- Playback follows the website's signed ticket, session and stream-resolution flow.
- An optional TMDB v3 key can provide catalog metadata directly.
- Configure an M3U playlist URL/path or direct HTTP(S) stream templates for alternative sources. Templates take precedence over Reely.
- Movie templates use `{id}`; TV templates use `{id}`, `{s}`, `{e}`. IDs are TMDB IDs. URLs must return video rather than HTML or JSON.

Reely currently allows the tested playback requests without sign-in. Account login, browser-only iframe fallbacks, and external subtitles are not implemented. Some titles may have no native stream; availability and API compatibility depend on the live service. Access errors are reported rather than bypassed. Search shows the first page supplied by Reely's search API.

## Development

Requires Python 3; no additional packages are needed for packaging or local tests.

```sh
python tests/test_addon.py
python build.py
```

Source lives in `plugin.video.reely/` and `repository.reely/`. Generated installable ZIPs live in `dist/`. Rebuild after editing the source.

Tested on Kodi 21.3 for Fire TV: catalog browsing and Reely-sourced Sintel playback in 1080p H.264 with AAC audio. Nine local tests passed. See [validation details](VALIDATION.txt). Other titles and Kodi versions have not all been tested.

## License

MIT; see [LICENSE](LICENSE). Original project copyright belongs to Vette1123 (Mohamed Gado). This is an unofficial adaptation, not an official Reely release. No credentials or private upstream server code are included.
