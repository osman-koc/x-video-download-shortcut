# X Video Downloader (iOS Shortcut)

An iPhone shortcut that downloads the video of an X (Twitter) post. Copy the post link, run the shortcut, pick what you want:

- **Video**: saved to Photos.
- **GIF**: you choose the section to keep, it is converted and saved to Photos.
- **WhatsApp sticker**: you trim a short clip, it is saved to Photos and WhatsApp opens so you can add it as a sticker.

The shortcut is English only. Runtime language detection did not work reliably in Shortcuts, so it was dropped. Other translations are kept in the repo for a future localized build.

> **Status:** the Mac run is verified up to the menu (clipboard, post ID, FxTwitter API, download, menu). Saving to Photos, GIF, WhatsApp sticker and everything on a physical iPhone are not tested yet. See [Known limitations](#known-limitations) and please open an issue if a step misbehaves.

## How it works

1. Reads the clipboard and extracts the post ID from an `x.com` / `twitter.com` link. If the clipboard has no valid link, it asks you to paste one.
2. Queries the public [FxTwitter API](https://github.com/FxEmbed/FxEmbed/wiki/Status-Fetch-API) (`api.fxtwitter.com/status/<id>`) and reads `tweet.media.all[0].url`, a direct MP4. X "GIFs" are MP4s too.
3. Downloads the MP4 and shows the menu.

How to copy the link on X: tap the share icon below the post, then **Copy link**.

## Install

iOS refuses unsigned shortcuts, and signing needs a Mac signed into iCloud (`shortcuts sign` fails on GitHub's macOS runners with "you must be signed into iCloud"). So you build and sign locally:

```sh
PYTHONPATH=src python3 -m xvideo_shortcut
shortcuts sign --mode anyone \
  --input dist/X-Video-Downloader.unsigned.shortcut \
  --output dist/X-Video-Downloader.shortcut
```

AirDrop `dist/X-Video-Downloader.shortcut` to the iPhone and open it in the Shortcuts app. On first run allow network access (`api.fxtwitter.com`, `video.twimg.com`) and Photos access. If iOS asks about pasting from the clipboard, choose **Allow Paste** (or set it to *Allow* in Settings > Apps > Shortcuts > Paste from Other Apps).

To troubleshoot, build with `--debug`: it shows the value of each key step (clipboard, post ID, API code, media URL, chosen action) in popups.

## Usage

- **Video**: pick *Video*.
- **GIF**: pick *GIF*, drag the handles in the trim screen to select the part to keep (shorter clips make smaller GIFs; a few seconds works best), confirm.
- **WhatsApp sticker**: pick *WhatsApp sticker*, trim to about 6 seconds, confirm. WhatsApp opens. Create a sticker from the clip in Photos and star it. Starred stickers live under **Favorites**, so no separate sticker pack is created for each clip.

### About WhatsApp stickers

WhatsApp does not allow Shortcuts (or any other app) to add stickers silently, and the Shortcuts app cannot produce animated WebP. The shortcut therefore prepares the clip and opens WhatsApp; the final add is done by you in WhatsApp's own sticker editor. Animated stickers must be at most 512x512 px, about 10 s and 500 KB; WhatsApp does the conversion and cropping in its editor.

## Build from source

Requires Python 3.9+ (no dependencies).

```sh
PYTHONPATH=src python -m xvideo_shortcut          # writes dist/X-Video-Downloader.unsigned.shortcut
python -m unittest discover -s tests -v           # run tests
```

Sign on a Mac (also done automatically by the `Build and sign shortcut` workflow when you push a `v*` tag):

```sh
shortcuts sign --mode anyone \
  --input dist/X-Video-Downloader.unsigned.shortcut \
  --output dist/X-Video-Downloader.shortcut
```

AirDrop the signed file to the iPhone. Alternatively, open the unsigned file in the Shortcuts app on macOS, which signs it on import, and let iCloud sync it.

### Jellycuts script

`jellycuts/X-Video-Downloader.jelly` is the same shortcut as a [Jellycuts](https://docs.jellycuts.com) script. Paste it into the Jellycuts app and export it to Shortcuts. It is generated from the same translations and constants (`PYTHONPATH=src python -m xvideo_shortcut --jelly jellycuts/X-Video-Downloader.jelly`); a test fails if the committed file is stale. Like the rest of the project it has not been run on a device.

### Project layout

```
src/xvideo_shortcut/
  model.py          minimal .shortcut (binary plist) writer
  flow.py           the shortcut's logic, action by action
  jelly.py          renders the same logic as a Jellycuts script
  i18n.py           loads translations
  translations/     one JSON file per language
tests/              structure, link-pattern and translation tests
.github/workflows/  CI: tests and an unsigned build artifact (signing needs a Mac)
```

### Translations (not used by the shortcut yet)

`src/xvideo_shortcut/translations/*.json` hold strings per language. The shortcut currently reads only `en.json`; the Jellycuts script still embeds all of them. Tests check that every language has every key.

## Known limitations

- Not yet verified on a real device; action parameters were written from the Shortcuts file format and may need adjustment on some iOS versions.
- Depends on the third-party FxTwitter service. If it is down or changes its API the shortcut stops working (error message: no video found).
- Private, deleted or age-restricted posts cannot be fetched. For posts with several videos only the first is used.
- Download only content you have the right to save. Respect the author's rights and X's terms.

## License

[MIT](LICENSE)
