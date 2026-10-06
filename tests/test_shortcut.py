import json
import plistlib
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xvideo_shortcut import i18n  # noqa: E402
from xvideo_shortcut.__main__ import build_shortcut  # noqa: E402
from xvideo_shortcut.flow import ID_AT_END_PATTERN, OPTION_KEYS, TWEET_ID_PATTERN  # noqa: E402


def load_actions():
    return plistlib.loads(build_shortcut())["WFWorkflowActions"]


def walk_refs(value):
    """Yield every Ref dict ({"Type": ...}) found inside a parameter value."""
    if isinstance(value, dict):
        if value.get("Type") in ("Variable", "ActionOutput") and ("VariableName" in value or "OutputUUID" in value):
            yield value
        for v in value.values():
            yield from walk_refs(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_refs(v)


class PlistStructure(unittest.TestCase):
    def setUp(self):
        self.actions = load_actions()

    def test_round_trips_as_binary_plist(self):
        data = build_shortcut()
        self.assertTrue(data.startswith(b"bplist00"))
        self.assertIn("WFWorkflowActions", plistlib.loads(data))

    def test_action_identifiers_and_uuids(self):
        uuids = set()
        for a in self.actions:
            self.assertTrue(a["WFWorkflowActionIdentifier"].startswith("is.workflow.actions."))
            u = a["WFWorkflowActionParameters"]["UUID"]
            self.assertNotIn(u, uuids)
            uuids.add(u)

    def test_references_point_backwards(self):
        seen_uuids, seen_vars = set(), set()
        for a in self.actions:
            params = a["WFWorkflowActionParameters"]
            for ref in walk_refs(params):
                if ref["Type"] == "ActionOutput":
                    self.assertIn(ref["OutputUUID"], seen_uuids, a["WFWorkflowActionIdentifier"])
                else:
                    self.assertIn(ref["VariableName"], seen_vars, a["WFWorkflowActionIdentifier"])
            seen_uuids.add(params["UUID"])
            if a["WFWorkflowActionIdentifier"].endswith(".setvariable"):
                seen_vars.add(params["WFVariableName"])

    def test_control_flow_is_balanced(self):
        stack = []
        for a in self.actions:
            if not a["WFWorkflowActionIdentifier"].endswith(".conditional"):
                continue
            p = a["WFWorkflowActionParameters"]
            mode = p["WFControlFlowMode"]
            if mode == 0:
                stack.append(p["GroupingIdentifier"])
            else:
                self.assertEqual(stack[-1], p["GroupingIdentifier"])
                if mode == 2:
                    stack.pop()
        self.assertEqual(stack, [])

    def test_failures_stop_the_shortcut(self):
        ids = [a["WFWorkflowActionIdentifier"] for a in self.actions]
        for i, name in enumerate(ids):
            if name.endswith(".alert") and "err" in json.dumps(self.actions[i]["WFWorkflowActionParameters"]):
                self.assertTrue(ids[i + 1].endswith(".exit"))


class TweetIdPattern(unittest.TestCase):
    def match(self, s):
        m = re.search(TWEET_ID_PATTERN, s, re.IGNORECASE)
        return m.group(1) if m else None

    def test_valid_links(self):
        cases = {
            "https://x.com/user/status/1234567890123456789?s=20": "1234567890123456789",
            "https://twitter.com/Some_User/status/42": "42",
            "https://mobile.twitter.com/u/status/7/video/1": "7",
            "https://x.com/i/status/99": "99",
            "https://x.com/i/web/status/98": "98",
            "https://fxtwitter.com/u/status/55": "55",
            "https://fixupx.com/u/status/56": "56",
            "check this https://x.com/u/status/123 out": "123",
        }
        for link, expected in cases.items():
            self.assertEqual(self.match(link), expected, link)

    def test_id_is_the_trailing_digits_of_the_match(self):
        link = "https://x.com/the1rain/status/2095254064753733864/video/1"
        whole = re.search(TWEET_ID_PATTERN, link, re.IGNORECASE).group(0)
        self.assertEqual(re.search(ID_AT_END_PATTERN, whole).group(0), "2095254064753733864")

    def test_invalid_links(self):
        for text in ["", "hello", "https://example.com/user/status/123", "https://x.com/user", "https://x.com/user/status/abc"]:
            self.assertIsNone(self.match(text), text)


class Translations(unittest.TestCase):
    def setUp(self):
        self.tables = i18n.load_translations()

    def test_all_languages_have_all_keys(self):
        keys = set(i18n.string_keys(self.tables))
        for code, table in self.tables.items():
            self.assertEqual(set(table) - {i18n.MARKER_KEY}, keys, code)
            self.assertTrue(i18n.era_markers(table), code)

    def test_option_labels_do_not_overlap(self):
        # The shortcut matches the chosen item with "Contains".
        for code, table in self.tables.items():
            labels = [table[k] for k in OPTION_KEYS]
            for a in labels:
                for b in labels:
                    if a is not b:
                        self.assertNotIn(a.lower(), b.lower(), code)

    def test_era_markers_are_unique_across_languages(self):
        markers = [m for t in self.tables.values() for m in i18n.era_markers(t)]
        self.assertEqual(len(markers), len(set(markers)))
        for a in markers:
            for b in markers:
                if a != b:
                    self.assertNotIn(a, b)


class ApiShape(unittest.TestCase):
    """The shortcut reads tweet -> media -> videos[0] -> url."""

    SAMPLE = {
        "code": 200,
        "tweet": {"media": {"videos": [{"type": "video", "url": "https://video.twimg.com/a.mp4"}]}},
    }

    def test_path(self):
        self.assertEqual(self.SAMPLE["tweet"]["media"]["videos"][0]["url"], "https://video.twimg.com/a.mp4")


if __name__ == "__main__":
    unittest.main()


class JellyScript(unittest.TestCase):
    def setUp(self):
        from xvideo_shortcut.jelly import TWEET_ID_PATTERN as JELLY_PATTERN, render

        self.tables = i18n.load_translations()
        self.script = render(self.tables)
        self.pattern = JELLY_PATTERN

    def test_committed_script_is_up_to_date(self):
        path = Path(__file__).resolve().parents[1] / "jellycuts" / "X-Video-Downloader.jelly"
        self.assertEqual(path.read_text(encoding="utf-8"), self.script)

    def test_every_translation_is_embedded(self):
        for table in self.tables.values():
            for key in i18n.string_keys(self.tables):
                self.assertIn(str(table[key]).replace('"', '\\"'), self.script)

    def test_braces_balance_and_no_backslash_regex(self):
        self.assertEqual(self.script.count("{"), self.script.count("}"))
        self.assertNotIn("\\d", self.pattern)
        self.assertNotIn("\\s", self.pattern)

    def test_pattern_matches_post_links(self):
        rx = re.compile(self.pattern, re.IGNORECASE)
        for url in (
            "https://x.com/user/status/1234567890?s=20",
            "https://twitter.com/i/web/status/42",
            "https://fxtwitter.com/a/status/7",
        ):
            self.assertIsNotNone(rx.search(url), url)
        self.assertIsNone(rx.search("https://example.com/status/1"))
