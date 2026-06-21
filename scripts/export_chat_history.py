#!/usr/bin/env python3
"""Export Cursor agent chat JSONL transcripts to readable Markdown."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

USER_QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL)
REDACTED_RE = re.compile(r"\n*\[REDACTED\]\n*")


def project_root() -> Path:
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("Could not locate project root (pyproject.toml not found)")


def cursor_project_slug(repo: Path) -> str:
    """Map a workspace path to Cursor's projects folder slug."""
    return repo.resolve().as_posix().lstrip("/").replace("/", "-")


def default_transcripts_dir() -> Path:
    """Cursor stores agent transcripts under ~/.cursor/projects/<slug>/agent-transcripts."""
    return Path.home() / ".cursor" / "projects" / cursor_project_slug(project_root()) / "agent-transcripts"


def discover_transcripts(transcripts_dir: Path) -> list[Path]:
    if not transcripts_dir.is_dir():
        return []
    return sorted(transcripts_dir.glob("**/*.jsonl"))


def extract_user_text(text: str) -> str:
    match = USER_QUERY_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def clean_assistant_text(text: str) -> str:
    text = REDACTED_RE.sub("\n", text)
    return text.strip()


def slugify(text: str, *, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        slug = "chat"
    return slug[:max_len].rstrip("-")


@dataclass
class ToolUse:
    name: str
    summary: str


@dataclass
class ChatTurn:
    user: str | None = None
    assistant_parts: list[str] = field(default_factory=list)
    tools: list[ToolUse] = field(default_factory=list)


def summarize_tool_use(item: dict) -> ToolUse:
    name = str(item.get("name", "unknown"))
    tool_input = item.get("input") or {}

    if name in {"Read", "Write", "StrReplace", "Delete"}:
        path = tool_input.get("path", "")
        summary = f"`{path}`" if path else "(no path)"
    elif name == "Shell":
        command = str(tool_input.get("command", "")).strip().replace("\n", " ")
        if len(command) > 120:
            command = command[:117] + "..."
        summary = f"`{command}`" if command else "(empty command)"
    elif name in {"Glob", "Grep", "SemanticSearch"}:
        pattern = tool_input.get("glob_pattern") or tool_input.get("pattern") or tool_input.get("query")
        summary = f"`{pattern}`" if pattern else json.dumps(tool_input, ensure_ascii=False)[:120]
    elif name == "WebFetch":
        summary = f"`{tool_input.get('url', '')}`"
    elif name == "WebSearch":
        summary = f"`{tool_input.get('search_term', '')}`"
    else:
        summary = json.dumps(tool_input, ensure_ascii=False)
        if len(summary) > 160:
            summary = summary[:157] + "..."

    return ToolUse(name=name, summary=summary)


def parse_transcript(jsonl_path: Path) -> list[ChatTurn]:
    turns: list[ChatTurn] = []
    current: ChatTurn | None = None

    with jsonl_path.open(encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{jsonl_path}:{line_no}: invalid JSON: {exc}") from exc

            if record.get("type") == "turn_ended":
                if current is not None and (current.user or current.assistant_parts or current.tools):
                    turns.append(current)
                    current = None
                continue

            role = record.get("role")
            message = record.get("message") or {}
            content = message.get("content") or []

            if role == "user":
                if current is not None and (current.user or current.assistant_parts or current.tools):
                    turns.append(current)
                current = ChatTurn()

                user_chunks: list[str] = []
                for item in content:
                    if item.get("type") == "text":
                        user_chunks.append(extract_user_text(str(item.get("text", ""))))
                current.user = "\n\n".join(chunk for chunk in user_chunks if chunk).strip() or None
                continue

            if role != "assistant":
                continue

            if current is None:
                current = ChatTurn()

            for item in content:
                item_type = item.get("type")
                if item_type == "text":
                    cleaned = clean_assistant_text(str(item.get("text", "")))
                    if cleaned:
                        current.assistant_parts.append(cleaned)
                elif item_type == "tool_use":
                    current.tools.append(summarize_tool_use(item))

    if current is not None and (current.user or current.assistant_parts or current.tools):
        turns.append(current)

    return turns


def first_user_line(turns: list[ChatTurn]) -> str:
    for turn in turns:
        if turn.user:
            first_line = turn.user.splitlines()[0].strip()
            if first_line:
                return first_line
    return "cursor-chat"


def render_tools(tools: list[ToolUse]) -> str:
    if not tools:
        return ""

    lines = [
        "",
        f"<details>",
        f"<summary>Tools used ({len(tools)})</summary>",
        "",
    ]
    for tool in tools:
        lines.append(f"- **{tool.name}**: {tool.summary}")
    lines.extend(["", "</details>", ""])
    return "\n".join(lines)


def render_turn(index: int, turn: ChatTurn, *, include_tools: bool) -> str:
    parts: list[str] = [f"## Turn {index}", ""]

    if turn.user:
        parts.extend(["### User", "", turn.user, ""])
    else:
        parts.extend(["### User", "", "*(no user message captured)*", ""])

    assistant_text = "\n\n".join(turn.assistant_parts).strip()
    parts.extend(["### Assistant", ""])
    if assistant_text:
        parts.append(assistant_text)
    else:
        parts.append("*(no assistant text captured)*")

    if include_tools and turn.tools:
        parts.append(render_tools(turn.tools))

    parts.append("")
    parts.append("---")
    parts.append("")
    return "\n".join(parts)


def render_transcript_markdown(
    jsonl_path: Path,
    turns: list[ChatTurn],
    *,
    include_tools: bool,
    generated_at: datetime,
) -> str:
    title = first_user_line(turns)
    if len(title) > 80:
        title = title[:77] + "..."

    header = [
        f"# {title}",
        "",
        f"- **Source:** `{jsonl_path}`",
        f"- **Chat ID:** `{jsonl_path.parent.name}`",
        f"- **Turns:** {len(turns)}",
        f"- **Exported:** {generated_at.isoformat()}",
        "",
        "---",
        "",
    ]

    body = [render_turn(i, turn, include_tools=include_tools) for i, turn in enumerate(turns, start=1)]
    return "\n".join(header + body)


def render_index_markdown(
    entries: list[tuple[Path, Path, list[ChatTurn]]],
    *,
    generated_at: datetime,
) -> str:
    lines = [
        "# Cursor chat history index",
        "",
        f"Exported: {generated_at.isoformat()}",
        "",
        "| # | Chat ID | Turns | First question | Output |",
        "|---|---------|-------|----------------|--------|",
    ]
    for index, (source, output_path, turns) in enumerate(entries, start=1):
        question = first_user_line(turns)
        if len(question) > 70:
            question = question[:67] + "..."
        rel_output = output_path.name
        lines.append(
            f"| {index} | `{source.parent.name}` | {len(turns)} | {question} | [{rel_output}]({rel_output}) |"
        )
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def export_transcript(
    jsonl_path: Path,
    output_path: Path,
    *,
    include_tools: bool,
    generated_at: datetime,
) -> list[ChatTurn]:
    turns = parse_transcript(jsonl_path)
    markdown = render_transcript_markdown(
        jsonl_path,
        turns,
        include_tools=include_tools,
        generated_at=generated_at,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return turns


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_out = project_root() / "docs" / "chat-history"
    parser = argparse.ArgumentParser(
        description="Export Cursor agent chat JSONL transcripts to Markdown.",
    )
    parser.add_argument(
        "--transcripts-dir",
        type=Path,
        default=default_transcripts_dir(),
        help=f"Directory with Cursor agent-transcripts (default: {default_transcripts_dir()})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_out,
        help=f"Directory for Markdown output (default: {default_out})",
    )
    parser.add_argument(
        "--chat-id",
        type=str,
        default=None,
        help="Export only one chat UUID (matches transcript folder or filename).",
    )
    parser.add_argument(
        "--starts-with",
        type=str,
        default=None,
        help="Export only chats whose first user message starts with this text (case-insensitive).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write a single chat to this file (requires exactly one matching transcript).",
    )
    parser.add_argument(
        "--include-tools",
        action="store_true",
        help="Include collapsible <details> sections listing tool calls.",
    )
    parser.add_argument(
        "--combined",
        action="store_true",
        help="Also write a single combined markdown file with all chats.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    transcripts_dir = args.transcripts_dir.resolve()
    output_dir = args.output_dir.resolve()
    generated_at = datetime.now(UTC).replace(microsecond=0)

    transcripts = discover_transcripts(transcripts_dir)
    if args.chat_id:
        transcripts = [
            path
            for path in transcripts
            if args.chat_id in path.as_posix()
        ]

    if args.starts_with:
        prefix = args.starts_with.casefold()
        matched: list[Path] = []
        for path in transcripts:
            turns = parse_transcript(path)
            first = first_user_line(turns).casefold()
            if first.startswith(prefix):
                matched.append(path)
        transcripts = matched

    if not transcripts:
        print(f"No transcript JSONL files found under {transcripts_dir}", file=sys.stderr)
        return 1

    if args.output is not None and len(transcripts) != 1:
        print(
            f"--output requires exactly one matching transcript, found {len(transcripts)}",
            file=sys.stderr,
        )
        return 1

    exported: list[tuple[Path, Path, list[ChatTurn]]] = []
    combined_parts: list[str] = []

    for jsonl_path in transcripts:
        turns = parse_transcript(jsonl_path)
        if not turns:
            print(f"Skipping empty transcript: {jsonl_path}")
            continue

        chat_id = jsonl_path.parent.name
        slug = slugify(first_user_line(turns))
        if args.output is not None:
            output_path = args.output.resolve()
        else:
            output_path = output_dir / f"{chat_id[:8]}-{slug}.md"

        export_transcript(
            jsonl_path,
            output_path,
            include_tools=args.include_tools,
            generated_at=generated_at,
        )
        exported.append((jsonl_path, output_path, turns))
        print(f"Wrote {output_path} ({len(turns)} turns)")

        if args.combined:
            combined_parts.append(
                render_transcript_markdown(
                    jsonl_path,
                    turns,
                    include_tools=args.include_tools,
                    generated_at=generated_at,
                )
            )

    if not exported:
        print("No non-empty transcripts exported.", file=sys.stderr)
        return 1

    if args.output is not None:
        return 0

    index_path = output_dir / "README.md"
    index_path.write_text(
        render_index_markdown(exported, generated_at=generated_at),
        encoding="utf-8",
    )
    print(f"Wrote {index_path}")

    if args.combined:
        combined_path = output_dir / "ALL_CHATS.md"
        combined_body = "\n\n".join(combined_parts)
        combined_path.write_text(combined_body, encoding="utf-8")
        print(f"Wrote {combined_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
