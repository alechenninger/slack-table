# slack-table

Convert Markdown, CSV, TSV, Cursor canvas, or simple pipe-delimited tables into
tab-separated rows that Slack pastes as a native table (default), or neatly
formatted Markdown tables with `--output markdown`.

It can also extract a table from an image using local Tesseract OCR, then render
the same Slack-native TSV.

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

# Format as Markdown, or copy Markdown using the same clipboard workflow.
slack-table table.csv --output markdown
slack-table --wait -q --output markdown

# The md-table command defaults to Markdown with all the same options.
md-table table.csv
md-table --wait -q

# Extract a table from an image.
slack-table --image table.png
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

Use `--output markdown` to get padded Markdown instead, with the first row as
the header:

```md
| Header A | Header B |
| -------- | -------- |
| Data 1A  | Data 1B  |
| Data 2A  | Data 2B  |
```

Use `--output slack` to explicitly select the default Slack output. The output
option works with every input mode and applies to both stdout and the clipboard.

## Install locally

Installing this package provides both `slack-table` and `md-table`.

```sh
brew install tesseract
python3 -m pip install -e .
```

With `pipx`, install Tesseract first and then install or reinstall the app so
the `tesserocr` dependency is added to the `pipx` environment:

```sh
brew install tesseract
pipx uninstall slack-table
pipx install -e .
```

You can also run it without installing:

```sh
PYTHONPATH=/path/to/slack-table/src python3 -m slack_table < table.md
```

## Input Formats

`slack-table` auto-detects Markdown tables, Cursor canvas copies, TSV, CSV, and
simple pipe-delimited rows. Use `--input markdown`, `--input cursor`,
`--input csv`, `--input tsv`, or `--input pipe` to force a parser.

Piped input and file input write the selected format to stdout. Interactive
clipboard input and `--wait` copy it back to the clipboard by default.

Image input uses `--image path/to/table.png` and runs locally. Supported image
files are PNG, JPEG, WEBP, and GIF. On macOS, the interactive clipboard modes
also detect an image on the clipboard automatically, so copying a table
screenshot and running `slack-table` or `slack-table --wait -q` works without
writing the image to a file first. Other operating systems report that image
clipboard input is unsupported.

Image OCR uses the `tesserocr` Python package, which is installed with
`slack-table`. Install Tesseract's native libraries before installing the
package. If embedded OCR is unavailable at runtime, `slack-table --image` falls
back to the `tesseract` command on `PATH`.

```sh
# Force embedded OCR or the command-line fallback.
slack-table --image table.png --image-engine tesserocr
slack-table --image table.png --image-engine tesseract
```

Use `--image-lang` to choose Tesseract languages, for example `eng+fra`, and
`--image-psm` to tune page segmentation mode. The default page segmentation mode
is `6`, which works well for many simple table screenshots.

## Shortcut

For the fastest flow, add an alias:

```sh
alias st='slack-table --wait -q'
```

Then copy a raw table, run `st`, and paste into Slack.
