"""Tests for Cursor chat transcript export."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from export_chat_history import (  # noqa: E402
    cursor_project_slug,
    extract_user_text,
    parse_transcript,
    render_transcript_markdown,
    summarize_tool_use,
)


def test_cursor_project_slug() -> None:
    repo = Path("/Users/yana/Projects/air-raid-alerts-analysis")
    assert cursor_project_slug(repo) == "Users-yana-Projects-air-raid-alerts-analysis"


def test_extract_user_text_strips_tags() -> None:
    raw = "<user_query>\nHello world\n</user_query>"
    assert extract_user_text(raw) == "Hello world"


def test_parse_transcript_groups_turns(tmp_path: Path) -> None:
    jsonl = tmp_path / "sample.jsonl"
    records = [
        {
            "role": "user",
            "message": {
                "content": [{"type": "text", "text": "<user_query>\nFirst question\n</user_query>"}]
            },
        },
        {
            "role": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Working...\n\n[REDACTED]"},
                    {"type": "tool_use", "name": "Read", "input": {"path": "docs/REQUIREMENTS.md"}},
                    {"type": "text", "text": "Here is the answer."},
                ]
            },
        },
        {"type": "turn_ended", "status": "success"},
        {
            "role": "user",
            "message": {
                "content": [{"type": "text", "text": "<user_query>\nSecond question\n</user_query>"}]
            },
        },
        {
            "role": "assistant",
            "message": {"content": [{"type": "text", "text": "Second answer."}]},
        },
    ]
    jsonl.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    turns = parse_transcript(jsonl)
    assert len(turns) == 2
    assert turns[0].user == "First question"
    assert turns[0].assistant_parts == ["Working...", "Here is the answer."]
    assert len(turns[0].tools) == 1
    assert turns[0].tools[0].name == "Read"
    assert turns[1].user == "Second question"
    assert turns[1].assistant_parts == ["Second answer."]


def test_render_transcript_markdown_includes_metadata(tmp_path: Path) -> None:
    jsonl = tmp_path / "chat.jsonl"
    jsonl.write_text(
        json.dumps(
            {
                "role": "user",
                "message": {
                    "content": [{"type": "text", "text": "<user_query>\nExport me\n</user_query>"}]
                },
            }
        )
        + "\n"
        + json.dumps(
            {
                "role": "assistant",
                "message": {"content": [{"type": "text", "text": "Done."}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    turns = parse_transcript(jsonl)
    markdown = render_transcript_markdown(
        jsonl,
        turns,
        include_tools=False,
        generated_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
    )
    assert "# Export me" in markdown
    assert "### User" in markdown
    assert "### Assistant" in markdown
    assert "Done." in markdown


def test_summarize_tool_use_shell_truncates() -> None:
    tool = summarize_tool_use(
        {
            "name": "Shell",
            "input": {"command": "echo " + ("x" * 200)},
        }
    )
    assert tool.name == "Shell"
    assert len(tool.summary) <= 123
