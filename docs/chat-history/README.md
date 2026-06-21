# Cursor chat history

Markdown exports of Cursor agent conversations for this project. Source files are JSONL transcripts stored locally by Cursor (not committed to git).

## Exports

| File | Chat ID | Turns | Description |
|------|---------|-------|-------------|
| [my-main-goal-chat.md](my-main-goal-chat.md) | `39becc87-809d-4dc3-b633-889e167fd7c4` | 27 | Project planning: requirements, data sources, pipeline, modeling, and early implementation |

For a machine-generated index of all exported chats, see [INDEX.md](INDEX.md) (created when you run a full export).

## Export script

From the repository root:

```bash
python3 scripts/export_chat_history.py --help
```

### Export one chat by first message

```bash
python3 scripts/export_chat_history.py \
  --starts-with "my main goal" \
  --output docs/chat-history/my-main-goal-chat.md \
  --include-tools
```

`--starts-with` matches the **first user message** (case-insensitive).

### Export by chat UUID

```bash
python3 scripts/export_chat_history.py \
  --chat-id 39becc87 \
  --output docs/chat-history/my-main-goal-chat.md
```

### Export all chats for this project

```bash
python3 scripts/export_chat_history.py --include-tools
```

Writes one Markdown file per chat under `docs/chat-history/` and updates [INDEX.md](INDEX.md).

### Options

| Flag | Purpose |
|------|---------|
| `--starts-with TEXT` | Filter to chats whose first user message starts with `TEXT` |
| `--chat-id UUID` | Filter to a specific transcript folder or filename |
| `--output PATH` | Write a single chat to `PATH` (exactly one match required) |
| `--output-dir DIR` | Output directory for multi-chat export (default: `docs/chat-history/`) |
| `--include-tools` | Add collapsible sections listing tool calls per turn |
| `--combined` | Also write `ALL_CHATS.md` with every chat in one file |
| `--transcripts-dir DIR` | Override Cursor transcript location |

Default transcript location:

```text
~/.cursor/projects/Users-yana-Projects-air-raid-alerts-analysis/agent-transcripts/
```

Each chat is a folder containing a `.jsonl` file.

## Format

Exported Markdown is structured as:

- **Title** — first user question
- **Metadata** — source path, chat ID, turn count, export timestamp
- **Turns** — alternating `### User` / `### Assistant` sections
- **Tools** (optional) — `<details>` blocks listing Read, Shell, Write, etc.

Assistant text has `[REDACTED]` placeholders removed. User messages have `<user_query>` wrappers stripped.

## Tests

```bash
pytest tests/test_export_chat_history.py -q
```

## Notes

- Re-export after new Cursor sessions to refresh Markdown.
- Transcripts live outside the repo; the script reads them from your local Cursor project folder.
- Large tool payloads are summarized, not copied in full.
