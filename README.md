# Vuecrest Summary Report

Browser automation captures PropVivo financial statements, saves HTML/table snapshots, and asks OpenAI to draft a markdown summary that can be browsed in the lightweight `report-viewer` UI.

## Installation

- Clone the repo and enter it:
  - `git clone <repo-url>`
  - `cd VuecrestSummaryReport`
- Install Python deps: `pip install -r requirements.txt`
- Install Playwright browsers: `python3 -m playwright install`
- Copy `/.env.example` to `/.env` and set credentials:
  - Required: `PROP_VIVO_USERNAME`, `PROP_VIVO_PASSWORD`
  - Optional: `OPENAI_API_KEY` (needed for summaries), `OUTPUT_DIR`, `HEADLESS`

## Summary Generation

- Run `python main.py` (or `python main.py --headless false` if you want to watch the browser).
- The script logs into PropVivo, visits Income Statement and Balance Sheet pages, saves snapshots under `data/html/<report>/<year>/<month>/`, converts tables to markdown, and writes the AI summary to `data/summaries/<year>/<month>/financial_summary.md`.
- `HEADLESS` in `.env` or `--headless` on the command controls Playwright headless mode; `OPENAI_API_KEY` must be present to request summaries.

## Web Service

The viewer expects the data directory to be reachable at `/data`.

- `cd report-viewer && ln -s ../data data` to expose the data folder at the server root.
- Start the service: `python report-viewer/server.py 8080` then open `http://localhost:8080/`.

## Navigation (what you see in the UI)

- The header shows the current data root (`data/`) and a `Reload` button to re-scan the data directory without refreshing the page.
- Left column lists months; chips (Summary/Income/Balance) light up when that file exists, and selecting a card focuses that month.
- The info bar shows the selected month and pills that open the Income Statement and Balance Sheet snapshots (table views) in new tabs.
- The main panel renders the markdown summary for the chosen month; placeholders explain what’s missing if a file cannot be found.
- A small status dot in the sidebar signals loading (busy), ready, or idle states while the data directory is parsed.

![Screen shot of dashboard.](/Screenshot.png)
