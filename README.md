# watch_and_convert

Watches a directory for new LAS files and converts each one to LAZ as soon as the exporting program finishes writing it.

## What it does

- Monitors the configured output folder with `watchdog`
- Waits until each `.las` file's size has been stable for 2 seconds (i.e. the exporter has closed it)
- Reads the file with `laspy`, sets the `point_source_id` field from the track number in the filename (e.g. `_Track03_` → `3`), and writes a compressed `.laz` alongside it
- Deletes the original `.las` once the `.laz` is confirmed on disk
- Processes files one at a time in a background thread; events are queued so nothing is missed

## Requirements

```
pip install watchdog laspy lazrs-python numpy
```

## Configuration

Edit the constants at the top of `watch_and_convert.py`:

| Constant | Default | Description |
|---|---|---|
| `WATCH_DIR` | `C:\Projectname\Export\LAS` | Folder to watch |
| `STABILITY_SECONDS` | `2.0` | Seconds of stable file size before conversion starts |
| `POLL_INTERVAL` | `0.5` | How often (seconds) to re-check file size |

## Usage

```
python watch_and_convert.py
```

Stop with `Ctrl+C`. The script logs each detected file, conversion start, and completion to the console.

## Filename convention

The track number is parsed from the filename with the pattern `_Track<N>_` (case-insensitive), according to Leica Pegasus Office convention. If no match is found the `point_source_id` field is left as-is.

Example: `Job_20260423_0808_Track03_Scanner1_1.las` → track `3`
