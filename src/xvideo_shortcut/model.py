"""Tiny object model for writing Shortcuts (.shortcut) property lists.

A shortcut is a binary plist holding a list of actions. Values that depend on
earlier results are expressed as "tokens": named variables or action outputs.
"""

from __future__ import annotations

import plistlib
import uuid
from typing import Any, Dict, List, Optional, Union

OBJECT_REPLACEMENT = "￼"
ACTION_PREFIX = "is.workflow.actions."


def new_uuid() -> str:
    return str(uuid.uuid4()).upper()


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


class Ref:
    """Reference to a value: a named variable or the output of an action."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @classmethod
    def variable(cls, name: str) -> "Ref":
        return cls({"Type": "Variable", "VariableName": name})

    @classmethod
    def output(cls, action_uuid: str, name: str) -> "Ref":
        return cls({"Type": "ActionOutput", "OutputUUID": action_uuid, "OutputName": name})

    def attachment(self) -> Dict[str, Any]:
        """Serialized form for parameters that take a single value."""
        return {"Value": dict(self.data), "WFSerializationType": "WFTextTokenAttachment"}


Part = Union[str, Ref]


def text(*parts: Part) -> Union[str, Dict[str, Any]]:
    """Build a text parameter, interpolating Refs. Plain str if no Refs used."""
    if not any(isinstance(p, Ref) for p in parts):
        return "".join(parts)  # type: ignore[arg-type]
    string = ""
    attachments: Dict[str, Any] = {}
    for part in parts:
        if isinstance(part, Ref):
            attachments["{%d, 1}" % _utf16_len(string)] = dict(part.data)
            string += OBJECT_REPLACEMENT
        else:
            string += part
    return {
        "Value": {"string": string, "attachmentsByRange": attachments},
        "WFSerializationType": "WFTextTokenString",
    }


class Action:
    def __init__(self, name: str, params: Dict[str, Any], output_name: str):
        self.name = name
        self.uuid = new_uuid()
        self.params = params
        self.output_name = output_name
        self.params["UUID"] = self.uuid

    @property
    def out(self) -> Ref:
        return Ref.output(self.uuid, self.output_name)

    def to_plist(self) -> Dict[str, Any]:
        return {
            "WFWorkflowActionIdentifier": ACTION_PREFIX + self.name,
            "WFWorkflowActionParameters": self.params,
        }


class IfBlock:
    """Context manager emitting If / Otherwise / End If."""

    def __init__(self, builder: "Builder", subject: Ref, condition: str, value: Optional[Part]):
        self.builder = builder
        self.group = new_uuid()
        params: Dict[str, Any] = {
            "GroupingIdentifier": self.group,
            "WFControlFlowMode": 0,
            "WFCondition": condition,
            "WFInput": {"Type": "Variable", "Variable": subject.attachment()},
        }
        if value is not None:
            params["WFConditionalActionString"] = text(value)
        builder.add("conditional", params, "If Result")

    def otherwise(self) -> None:
        self.builder.add(
            "conditional",
            {"GroupingIdentifier": self.group, "WFControlFlowMode": 1},
            "If Result",
        )

    def __enter__(self) -> "IfBlock":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.builder.add(
                "conditional",
                {"GroupingIdentifier": self.group, "WFControlFlowMode": 2},
                "If Result",
            )


class Builder:
    def __init__(self, debug: bool = False) -> None:
        self.actions: List[Action] = []
        self.debug = debug

    def trace(self, label: str, value: Ref) -> None:
        """In debug builds, show `label: value` on screen (to find where a run goes wrong)."""
        if self.debug:
            self.add("showresult", {"Text": text(label + ": ", value)})

    def add(self, name: str, params: Optional[Dict[str, Any]] = None, output_name: str = "Result") -> Action:
        action = Action(name, dict(params or {}), output_name)
        self.actions.append(action)
        return action

    def if_(self, subject: Ref, condition: str, value: Optional[Part] = None) -> IfBlock:
        return IfBlock(self, subject, condition, value)

    def set_var(self, name: str, value: Optional[Ref] = None) -> Ref:
        params: Dict[str, Any] = {"WFVariableName": name}
        if value is not None:
            params["WFInput"] = value.attachment()
        self.add("setvariable", params)
        return Ref.variable(name)

    def to_plist(self, icon_color: int, icon_glyph: int) -> Dict[str, Any]:
        return {
            "WFWorkflowClientVersion": "2900.0.1",
            "WFWorkflowMinimumClientVersion": 900,
            "WFWorkflowMinimumClientVersionString": "900",
            "WFWorkflowIcon": {
                "WFWorkflowIconStartColor": icon_color,
                "WFWorkflowIconGlyphNumber": icon_glyph,
            },
            "WFWorkflowImportQuestions": [],
            "WFWorkflowInputContentItemClasses": [],
            "WFWorkflowTypes": [],
            "WFWorkflowActions": [a.to_plist() for a in self.actions],
        }

    def dumps(self, icon_color: int, icon_glyph: int) -> bytes:
        return plistlib.dumps(self.to_plist(icon_color, icon_glyph), fmt=plistlib.FMT_BINARY)
