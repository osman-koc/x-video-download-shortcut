# Changelog

## 1.0.0

First release.

### What it does
- Saves the video of an X (Twitter) post to Photos and shows a notification.
- Works from the X app's Share Sheet: share a post and pick **X Video Downloader**. Run on its own, it uses the link in the clipboard, and asks for a link if neither has one.
- Gets a direct MP4 from the public [FxTwitter API](https://github.com/FxEmbed/FxEmbed/wiki/Status-Fetch-API) (X "GIFs" are MP4s too).
- Shows a clear message for photo-only, private, deleted or invalid posts.

### Install
- One-tap link in the [README](README.md), or build and sign it yourself on a Mac with `./scripts/build-and-sign.sh`.

### Not supported
- GIF conversion (saving the converted GIF to Photos did not work) and WhatsApp stickers (WhatsApp's sticker maker on iPhone does not accept videos or GIFs).
- The shortcut is English only.

### Known limitations
- Depends on the third-party FxTwitter service.
- Only the first media item of a post is downloaded.
