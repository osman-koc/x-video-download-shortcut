"""The shortcut's logic, written as a sequence of Shortcuts actions."""

from __future__ import annotations

from typing import Dict

from . import i18n
from .model import Builder, Ref, text

API_URL = "https://api.fxtwitter.com/status/"

# Finds the numeric post ID in x.com / twitter.com (and fx/vx mirror) links,
# including "i/status/<id>" and "i/web/status/<id>" forms.
TWEET_ID_PATTERN = r"(?:^|[/.])(?:fx|vx|fixup)?(?:twitter|x)\.com/(?:[^/\s]+/)*?status(?:es)?/(\d+)"

# Applied to the text matched by TWEET_ID_PATTERN, which ends with the numeric ID.
ID_AT_END_PATTERN = r"[0-9]+$"



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
    """Expose each (English) string as a variable.

    Runtime language detection was dropped: the shortcut is English only. The other
    translation files are kept for a future localized build.
    """
    english = tables[i18n.DEFAULT_LANGUAGE]
    keys = i18n.string_keys(tables)
    for key in keys:
        b.add("gettext", {"WFTextActionText": str(english[key])}, "Text")
        b.set_var("s_" + key, b.actions[-1].out)
    b.trace("app_name string", Ref.variable("s_app_name"))
    return {key: Ref.variable("s_" + key) for key in keys}


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

    # The match ends with the post ID, so a second match on its trailing digits yields it
    # without relying on regex capture groups.
    digits = b.add(
        "text.match",
        {
            "WFMatchTextPattern": ID_AT_END_PATTERN,
            "WFMatchTextCaseSensitive": False,
            "text": text(Ref.variable("matches")),
        },
        "Matches",
    )
    tweet_id = b.set_var("tweet_id", digits.out)
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
    b.trace("video file", video)

    b.add("savetocameraroll", {"WFInput": video.attachment()})
    b.trace("saved to Photos")
    _save_notification(b, s, "done_video")
