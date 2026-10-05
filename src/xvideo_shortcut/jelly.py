"""Renders the shortcut as a Jellycuts (Jelly language) script.

Same logic as flow.py, written against the Shortcuts Standard library
documented at https://docs.jellycuts.com. Paste the output into the Jellycuts
app and export it to Shortcuts. Translations come from translations/*.json.
"""

from __future__ import annotations

from typing import Dict, List

from . import i18n
from .flow import API_URL, OPTION_KEYS, WHATSAPP_URL

# Jelly strips backslashes from strings, so the pattern avoids \d, \s and \. .
TWEET_ID_PATTERN = r"(?:^|[/.])(?:fx|vx|fixup)?(?:twitter|x)[.]com/(?:[^/ ]+/)*?status(?:es)?/([0-9]+)"

HEADER = "import Shortcuts\n#Color: blue, #Icon: downloadArrow\n"


def _camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(p.capitalize() for p in rest)


def _lit(value: str) -> str:
    if "\\" in value or "${" in value:
        raise ValueError(f"Not representable in a Jelly string: {value!r}")
    return '"' + value.replace('"', '\\"') + '"'


def _fail(message_key: str, indent: str) -> List[str]:
    return [
        f'{indent}alert(alert: "${{{_camel(message_key)}}}", title: "${{appName}}", cancel: false)',
        f"{indent}exit()",
    ]


def render(tables: Dict[str, Dict[str, object]]) -> str:
    keys = i18n.string_keys(tables)
    en = tables[i18n.DEFAULT_LANGUAGE]
    out: List[str] = [HEADER, "// Localization: English first, then overridden by the phone's language."]
    out += [f"var {_camel(k)} = {_lit(en[k])}" for k in keys]  # type: ignore[arg-type]

    out += [
        "",
        "// The Gregorian era (AD, MS, n. Chr. ...) is spelled per locale, which reveals the language.",
        'formatDate(date: "${Current Date}", dStyle: Custom, tStyle: None, custom: "G") >> era',
    ]
    for code, table in tables.items():
        if code == i18n.DEFAULT_LANGUAGE:
            continue
        for marker in i18n.era_markers(table):
            out.append(f"if(era .contains {_lit(marker)}) {{")
            out += [f"    {_camel(k)} = {_lit(table[k])}" for k in keys]  # type: ignore[arg-type]
            out.append("}")

    pattern = _lit(TWEET_ID_PATTERN)
    out += [
        "",
        "// Post ID from the clipboard, or ask for a link.",
        "getClipboard() >> clip",
        f'matchText(text: "${{clip}}", regex: {pattern}, caseSensitive: false) >> firstMatch',
        "var matches = firstMatch",
        "if(matches == nil) {",
        '    askForInput(prompt: "${askLink}", type: Text) >> pasted',
        f'    matchText(text: "${{pasted}}", regex: {pattern}, caseSensitive: false) >> secondMatch',
        "    matches = secondMatch",
        "    if(matches == nil) {",
        *_fail("err_invalid_link", "        "),
        "    }",
        "}",
        'getMatchGroup(type: Group At Index, matches: matches, index: "1") >> tweetId',
        "",
        "// FxTwitter returns the direct MP4 URL (X GIFs are MP4s too).",
        f'downloadURL(url: "{API_URL}${{tweetId}}") >> response',
        "getDictionaryFrom(input: response) >> parsed",
        "var post = parsed.key(tweet)",
        "var mediaInfo = post.key(media)",
        "var videos = mediaInfo.key(videos)",
        "if(videos == nil) {",
        *_fail("err_no_video", "    "),
        "}",
        "getItemFromList(list: videos, type: First Item) >> firstVideo",
        "var videoURL = firstVideo.key(url)",
        'downloadURL(url: "${videoURL}") >> video',
        "",
        "// Menu: Menu cases cannot contain variables, so use list + choose to stay localized.",
        "list(items: [" + ", ".join(f'"${{{_camel(k)}}}"' for k in OPTION_KEYS) + "]) >> options",
        'choose(list: options, prompt: "${choosePrompt}") >> choice',
        "",
        'if(choice .contains "${optVideo}") {',
        "    saveToCameraRoll(image: video)",
        '    sendNotification(body: "${doneVideo}", title: "${appName}")',
        "}",
        "",
        "// The trim screen lets the user pick the section that becomes the GIF.",
        'if(choice .contains "${optGif}") {',
        "    trimVideo(video: video) >> gifClip",
        "    makeGIF(content: gifClip) >> gif",
        "    saveToCameraRoll(image: gif)",
        '    sendNotification(body: "${doneGif}", title: "${appName}")',
        "}",
        "",
        "// WhatsApp has no sticker automation: save a short clip, then hand over to WhatsApp.",
        'if(choice .contains "${optSticker}") {',
        "    trimVideo(video: video) >> stickerClip",
        "    saveToCameraRoll(image: stickerClip)",
        '    alert(alert: "${stickerHowto}", title: "${appName}", cancel: false)',
        f'    openURL(url: "{WHATSAPP_URL}")',
        "}",
        "",
    ]
    return "\n".join(out)
