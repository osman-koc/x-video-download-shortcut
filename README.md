<p align="center">
  <img src="assets/icon.png" width="128" alt="X Video Downloader icon">
</p>

<h1 align="center">X Video Downloader</h1>

<p align="center">
  An iPhone shortcut that saves the video of an X (Twitter) post to Photos.<br>
  Copy the post link, run the shortcut, done.
</p>

## Get the shortcut

1. Open the shortcut link on your iPhone: **[Add to Shortcuts](#install)**
2. Tap **Add Shortcut**.
3. First run: allow network access (`api.fxtwitter.com`, `video.twimg.com`) and Photos access.

## How to use

1. In the X app, tap the share icon below a post with a video, then **Copy link**.
2. Run **X Video Downloader** (from the Shortcuts app, or add it to the Home Screen or Siri).
3. The video is saved to Photos and a notification confirms it.

If the clipboard has no X post link, the shortcut asks you to paste one. If iOS asks about pasting from the clipboard, choose **Allow Paste** (or Settings > Apps > Shortcuts > Paste from Other Apps > *Allow*).

## How it works

1. Reads the clipboard and extracts the post ID from an `x.com` / `twitter.com` link.
2. Queries the public [FxTwitter API](https://github.com/FxEmbed/FxEmbed/wiki/Status-Fetch-API) (`api.fxtwitter.com/status/<id>`) and reads `tweet.media.all[0].url`, a direct MP4. X "GIFs" are MP4s too.
3. Downloads the MP4, saves it to Photos and shows a notification.

## Install

iOS only imports **signed** shortcuts, and signing needs a Mac signed into iCloud (`shortcuts sign` fails on CI runners with "you must be signed into iCloud"). Build and sign it yourself:

```sh
git clone https://github.com/osman-koc/x-video-download-shortcut
cd x-video-download-shortcut
./scripts/build-and-sign.sh      # needs macOS and Python 3.9+
```

This writes `dist/X Video Downloader.shortcut`. Open it on the Mac, or AirDrop it to the iPhone. The file name is the shortcut's name in the Shortcuts app, so keep it as is.

To share a one-tap install link, open the shortcut in the Shortcuts app, tap **Share > Copy iCloud Link**, and publish that link.

## Not supported

- **GIF conversion**: saving a converted GIF to Photos did not work, so it was removed.
- **WhatsApp stickers**: WhatsApp's sticker maker on iPhone does not accept videos or GIFs, and Shortcuts cannot add stickers to WhatsApp. Animated stickers need a third-party sticker app, which can import the saved video from Photos.
- The shortcut is English only.

## Limitations

- Depends on the third-party FxTwitter service. If it is down or changes its API the shortcut stops working (message: no video found).
- Private, deleted or age-restricted posts cannot be fetched. For posts with several media items only the first is used, and photo-only posts are rejected.
- Download only content you have the right to save. Respect the author's rights and X's terms.

## Troubleshooting

Build a debug version that shows the value of each step (clipboard, post ID, API code, media URL, saved) in popups:

```sh
PYTHONPATH=src python3 -m xvideo_shortcut --debug -o "dist/X Video Downloader.unsigned.shortcut"
```

Then sign it as above. Common cases: an empty `clipboard` popup means the copied link was replaced (do not copy popup text while testing); `api code: 404` means the post ID was not found.

## Development

```sh
python -m unittest discover -s tests -v    # run tests (Python 3.9+, no dependencies)
```

```
src/xvideo_shortcut/
  model.py     minimal .shortcut (binary plist) writer
  flow.py      the shortcut's logic, action by action
  strings.py   user-facing messages
scripts/       build-and-sign.sh (macOS)
tests/         structure and link-pattern tests
assets/        icon (SVG + PNG)
.github/       CI: tests and an unsigned build artifact
```

The Shortcuts app has no file format documentation; action parameters were written from the format as observed and checked on a device, so a future iOS release may need adjustments.

## License

[MIT](LICENSE)
