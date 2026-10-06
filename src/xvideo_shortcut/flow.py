"""The shortcut's logic, written as a sequence of Shortcuts actions."""

from __future__ import annotations

from typing import Dict

from . import i18n
from .model import Builder, Ref, new_uuid, text

API_URL = "https://api.fxtwitter.com/status/"
WHATSAPP_URL = "whatsapp://"

# Finds the numeric post ID in x.com / twitter.com (and fx/vx mirror) links,
# including "i/status/<id>" and "i/web/status/<id>" forms.
TWEET_ID_PATTERN = r"(?:^|[/.])(?:fx|vx|fixup)?(?:twitter|x)\.com/(?:[^/\s]+/)*?status(?:es)?/(\d+)"

# Applied to the text matched by TWEET_ID_PATTERN, which ends with the numeric ID.
ID_AT_END_PATTERN = r"[0-9]+$"

OPTION_KEYS = ("opt_video", "opt_gif", "opt_sticker")
ACTION_VIDEO, ACTION_GIF, ACTION_STICKER = "video", "gif", "sticker"
ACTION_CODES = (ACTION_VIDEO, ACTION_GIF, ACTION_STICKER)


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


def _choose_action(b: Builder, tables: Dict[str, Dict[str, object]]) -> Ref:
    """Show the menu and store the choice as a fixed code in `action`."""
    english = tables[i18n.DEFAULT_LANGUAGE]
    group = new_uuid()
    titles = [str(english[k]) for k in OPTION_KEYS]
    b.add(
        "choosefrommenu",
        {
            "GroupingIdentifier": group,
            "WFControlFlowMode": 0,
            "WFMenuPrompt": str(english["choose_prompt"]),
            "WFMenuItems": titles,
        },
    )
    for title, action_code in zip(titles, ACTION_CODES):
        b.add(
            "choosefrommenu",
            {"GroupingIdentifier": group, "WFControlFlowMode": 1, "WFMenuItemTitle": title},
        )
        b.add("gettext", {"WFTextActionText": action_code}, "Text")
        b.set_var("action", b.actions[-1].out)
    b.add("choosefrommenu", {"GroupingIdentifier": group, "WFControlFlowMode": 2})
    return Ref.variable("action")


def build_flow(b: Builder, tables: Dict[str, Dict[str, object]]) -> None:
    s = _localize(b, tables)
    tweet_id = _resolve_tweet_id(b, s)
    video_url = _fetch_video_url(b, s, tweet_id)

    video = b.set_var(
        "video",
        b.add("downloadurl", {"WFURL": text(video_url), "WFHTTPMethod": "GET"}, "Contents of URL").out,
    )
    b.trace("video file", video)

    action = _choose_action(b, tables)
    b.trace("action", action)

    with b.if_(action, "Contains", ACTION_VIDEO):
        b.add("savetocameraroll", {"WFInput": video.attachment()})
        _save_notification(b, s, "done_video")

    with b.if_(action, "Contains", ACTION_GIF):
        # The Trim Media screen lets the user pick the section that becomes the GIF.
        trimmed = b.add("trimvideo", {"WFInput": video.attachment()}, "Trimmed Media")
        gif = b.add("makegif", {"WFInput": trimmed.out.attachment()}, "GIF")
        b.add("savetocameraroll", {"WFInput": gif.out.attachment()})
        _save_notification(b, s, "done_gif")

    with b.if_(action, "Contains", ACTION_STICKER):
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
