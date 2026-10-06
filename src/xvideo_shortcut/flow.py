"""The shortcut's logic, written as a sequence of Shortcuts actions."""

from __future__ import annotations

import json
from typing import Dict

from . import i18n
from .model import Builder, Ref, text

API_URL = "https://api.fxtwitter.com/status/"
WHATSAPP_URL = "whatsapp://"

# Finds the numeric post ID in x.com / twitter.com (and fx/vx mirror) links,
# including "i/status/<id>" and "i/web/status/<id>" forms.
TWEET_ID_PATTERN = r"(?:^|[/.])(?:fx|vx|fixup)?(?:twitter|x)\.com/(?:[^/\s]+/)*?status(?:es)?/(\d+)"

OPTION_KEYS = ("opt_video", "opt_gif", "opt_sticker")


def _dict_value(b: Builder, source: Ref, key) -> Ref:
    action = b.add(
        "getvalueforkey",
        {
            "WFInput": source.attachment(),
            "WFDictionaryKey": key,
            "WFGetDictionaryValueType": "Value",
        },
        "Dictionary Value",
    )
    return action.out


def _localize(b: Builder, tables: Dict[str, Dict[str, object]]) -> Dict[str, Ref]:
    """Pick the phone's language at runtime and expose each string as a variable.

    The era of the Gregorian calendar ("AD", "MS", "n. Chr." ...) is spelled
    per locale but never changes with the date, so formatting today's date
    with the era pattern reveals the device language.
    """
    b.add("gettext", {"WFTextActionText": i18n.DEFAULT_LANGUAGE}, "Text")
    lang = b.set_var("lang", b.actions[-1].out)

    now = b.add("date", {"WFDateActionMode": "Current Date"}, "Date")
    era = b.add(
        "format.date",
        {"WFDate": now.out.attachment(), "WFDateFormatStyle": "Custom", "WFDateFormat": "G"},
        "Formatted Date",
    )
    era_var = b.set_var("era", era.out)

    for code, table in tables.items():
        for marker in i18n.era_markers(table):
            with b.if_(era_var, "Contains", marker):
                b.add("gettext", {"WFTextActionText": code}, "Text")
                b.set_var("lang", b.actions[-1].out)

    payload = {code: {k: v for k, v in t.items() if k != i18n.MARKER_KEY} for code, t in tables.items()}
    b.add("gettext", {"WFTextActionText": json.dumps(payload, ensure_ascii=False)}, "Text")
    b.add("detect.dictionary", {}, "Dictionary")
    all_strings = b.set_var("all_strings")
    table = b.set_var("strings", _dict_value(b, all_strings, text(lang)))

    refs: Dict[str, Ref] = {}
    for key in i18n.string_keys(tables):
        refs[key] = b.set_var("s_" + key, _dict_value(b, table, key))
    return refs


def _fail(b: Builder, s: Dict[str, Ref], message_key: str) -> None:
    b.add(
        "alert",
        {
            "WFAlertActionTitle": text(s["app_name"]),
            "WFAlertActionMessage": text(s[message_key]),
            "WFAlertActionCancelButtonShown": False,
        },
    )
    b.add("exit")


def _extract_tweet_id(b: Builder, source: Ref) -> Ref:
    """Match the pattern against `source`; returns the matches reference."""
    return b.add(
        "text.match",
        {
            "WFMatchTextPattern": TWEET_ID_PATTERN,
            "WFMatchTextCaseSensitive": False,
            "text": text(source),
        },
        "Matches",
    ).out


def _resolve_tweet_id(b: Builder, s: Dict[str, Ref]) -> Ref:
    """Use the clipboard if it holds a post link, otherwise ask for one."""
    clipboard = b.set_var("clipboard", b.add("getclipboard", {}, "Clipboard").out)
    # The clipboard may hold a URL or rich text item; match against plain text.
    clip_text = b.add("detect.text", {"WFInput": clipboard.attachment()}, "Text").out
    b.trace("clipboard", clip_text)
    matches = _extract_tweet_id(b, clip_text)
    b.set_var("matches", matches)
    b.trace("matches", matches)

    with b.if_(Ref.variable("matches"), "Does Not Have Any Value"):
        asked = b.add(
            "ask",
            {"WFAskActionPrompt": text(s["ask_link"]), "WFInputType": "Text"},
            "Provided Input",
        )
        pasted = b.set_var("pasted", asked.out)
        b.set_var("matches", _extract_tweet_id(b, pasted))
        with b.if_(Ref.variable("matches"), "Does Not Have Any Value"):
            _fail(b, s, "err_invalid_link")

    group = b.add(
        "text.match.getgroup",
        {
            "WFInput": Ref.variable("matches").attachment(),
            "WFGetGroupType": "Group At Index",
            "WFGroupIndex": 1,
        },
        "Group",
    )
    tweet_id = b.set_var("tweet_id", group.out)
    b.trace("tweet_id", tweet_id)
    return tweet_id


def _fetch_video_url(b: Builder, s: Dict[str, Ref], tweet_id: Ref) -> Ref:
    response = b.add(
        "downloadurl",
        {"WFURL": text(API_URL, tweet_id), "WFHTTPMethod": "GET", "ShowHeaders": False},
        "Contents of URL",
    )
    parsed = b.add("detect.dictionary", {"WFInput": response.out.attachment()}, "Dictionary")
    if b.debug:
        b.trace("api code", _dict_value(b, parsed.out, "code"))
    post = _dict_value(b, parsed.out, "tweet")
    media = _dict_value(b, post, "media")
    # `all` keeps the post's media in order; a post holds either photos or one video/GIF.
    items = b.set_var("media_items", _dict_value(b, media, "all"))
    b.trace("media items", items)

    with b.if_(items, "Does Not Have Any Value"):
        _fail(b, s, "err_no_video")

    first = b.add(
        "getitemfromlist",
        {"WFInput": items.attachment(), "WFItemSpecifier": "First Item"},
        "Item from List",
    )
    first_item = b.set_var("first_media", first.out)
    kind = b.set_var("media_type", _dict_value(b, first_item, "type"))
    b.trace("media_type", kind)
    with b.if_(kind, "Contains", "photo"):
        _fail(b, s, "err_no_video")

    video_url = b.set_var("video_url", _dict_value(b, first_item, "url"))
    b.trace("video_url", video_url)
    with b.if_(video_url, "Does Not Have Any Value"):
        _fail(b, s, "err_no_video")
    return video_url


def _save_notification(b: Builder, s: Dict[str, Ref], key: str) -> None:
    b.add(
        "notification",
        {"WFNotificationActionTitle": text(s["app_name"]), "WFNotificationActionBody": text(s[key])},
    )


def build_flow(b: Builder, tables: Dict[str, Dict[str, object]]) -> None:
    s = _localize(b, tables)
    tweet_id = _resolve_tweet_id(b, s)
    video_url = _fetch_video_url(b, s, tweet_id)

    video = b.set_var(
        "video",
        b.add("downloadurl", {"WFURL": text(video_url), "WFHTTPMethod": "GET"}, "Contents of URL").out,
    )

    b.add("list", {"WFItems": [text(s[k]) for k in OPTION_KEYS]}, "List")
    choice = b.set_var(
        "choice",
        b.add("choosefromlist", {"WFChooseFromListActionPrompt": text(s["choose_prompt"])}, "Chosen Item").out,
    )

    with b.if_(choice, "Contains", s["opt_video"]):
        b.add("savetocameraroll", {"WFInput": video.attachment()})
        _save_notification(b, s, "done_video")

    with b.if_(choice, "Contains", s["opt_gif"]):
        # The Trim Media screen lets the user pick the section that becomes the GIF.
        trimmed = b.add("trimvideo", {"WFInput": video.attachment()}, "Trimmed Media")
        gif = b.add("makegif", {"WFInput": trimmed.out.attachment()}, "GIF")
        b.add("savetocameraroll", {"WFInput": gif.out.attachment()})
        _save_notification(b, s, "done_gif")

    with b.if_(choice, "Contains", s["opt_sticker"]):
        # WhatsApp offers no automation for its sticker library: save a short
        # clip, then hand over to WhatsApp, where it is added once.
        trimmed = b.add("trimvideo", {"WFInput": video.attachment()}, "Trimmed Media")
        b.add("savetocameraroll", {"WFInput": trimmed.out.attachment()})
        b.add(
            "alert",
            {
                "WFAlertActionTitle": text(s["app_name"]),
                "WFAlertActionMessage": text(s["sticker_howto"]),
                "WFAlertActionCancelButtonShown": False,
            },
        )
        link = b.add("url", {"WFURLActionURL": WHATSAPP_URL}, "URL")
        b.add("openurl", {"WFInput": link.out.attachment()})
