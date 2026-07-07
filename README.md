# slack-table

Convert Markdown, CSV, TSV, or simple pipe-delimited tables into tab-separated
rows that Slack pastes as a native table.

Slack's Block Kit table block is represented well by copied tab-separated rows:
copying a rendered table from Block Kit Builder produces TSV, and pasting TSV
into Slack creates the native table experience.

## Usage

```sh
# Pipe input, print Slack table paste data.
cat table.md | slack-table

# Pipe input and copy the result.
cat table.md | slack-table --copy

# Fast mode: copy a raw table, run this, then paste into Slack.
slack-table

# Wait for the next clipboard change, convert it, copy the result, and exit.
slack-table --wait -q

# Read a file.
slack-table table.md
```

Example input:

```md
| Header A | Header B |
| --- | --- |
| Data 1A | Data 1B |
| Data 2A | Data 2B |
```

Clipboard/output:

```text
Header A	Header B
Data 1A	Data 1B
Data 2A	Data 2B
```

Paste that into Slack to get a native Slack table.

## Install locally

```sh
python3 -m pip install -e .
```

You can also run it without installing:

```sh
PYTHONPATH=/path/to/slack-table/src python3 -m slack_table < table.md
```

## Input Formats

`slack-table` auto-detects Markdown tables, TSV, CSV, and simple pipe-delimited
rows. Use `--input markdown`, `--input csv`, `--input tsv`, or `--input pipe` to
force a parser.

Piped input and file input write TSV to stdout by default. Interactive clipboard
input and `--wait` copy the converted TSV back to the clipboard by default.

## Shortcut

For the fastest flow, add an alias:

```sh
alias st='slack-table --wait -q'
```

Then copy a raw table, run `st`, and paste into Slack.
