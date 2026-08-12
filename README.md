# 835 → MIR Converter (UI + CLI)

This project converts X12 835 claim/payment data into the fixed-width MIR/MO structure reverse-engineered from the supplied production sample and proprietary MIR specification.

It also ships an **agentic, terminal-based AI assistant** (`main.py`) and a **local web-based agentic chatbot** (React + FastAPI + Ollama) that understands natural language, analyzes the 835, searches/filters claims, and generates MIR files — powered entirely by a local **Ollama / Llama 3.2** model.

## Local web chatbot (new)

A simple "ChatGPT for your 835": upload a file in the browser, chat with a local
Llama 3.2 agent, and download generated `.mir` files (individually or as a ZIP).

- Frontend: React + Vite at `http://localhost:5173`
- Backend: FastAPI at `http://localhost:8000`
- AI: local Ollama / `llama3.2` only — no cloud AI, no external servers
- Uploaded 835s and generated MIRs stay on your PC under `data/`

### Setup (one time)

Requirements: Python 3.12, Node.js LTS, and [Ollama](https://ollama.com).

```
setup.bat
```

`setup.bat` creates `.venv`, installs Python + Node dependencies, builds the
frontend, and pulls the `llama3.2` model into Ollama if it is missing.

### Start

```
start.bat
```

This checks/starts Ollama, launches the FastAPI backend and the Vite frontend in
two windows, then opens `http://localhost:5173`.

### Using the app

1. Click **Upload 835 File** and pick your `.835` file.
2. The system uploads, parses, and analyzes it (you see the claim count).
3. Chat naturally. Examples:

   - `Hi`
   - `How many claims are there?`
   - `Find Ashay's claim.`
   - `Which claim has the highest payment?`
   - `Find claims above 5000.`
   - `Show me the details of claim CLM12345.`
   - `Generate MIR for the second one.`
   - `Generate MIR for all Ashay's claims.`

4. When an MIR is generated you get **[Download]** buttons for each file and a
   **[Download All (ZIP)]** button. Downloads return the actual generated files.

The status bar in the top-right shows whether Backend, Ollama, and Llama 3.2 are
online. If Ollama is down, the UI tells you to start it instead of silently
falling back to a cloud API.

### How it works

> The AI decides *what* to do; deterministic Python performs the actual work.

End-to-end flow:

```
You upload a .835 file  (POST /api/files/upload)
        │
        ▼
edi835_parser.py  ── parses the 835 once into structured Claim objects
tools/analysis.py ── builds a summary (claim count, totals, payer)
        │
        ▼
You chat  (POST /api/chat)
        │
        ▼
agent/ (Llama 3.2)  ── decides WHICH tool to call (search / filter /
                        details / generate MIR). It only plans — it never
                        touches the raw file.
        │
        ▼
tools/  ── run deterministically over the parsed claims
   search_claims.py   find "Ashay"  → matching claims
   claim_details.py   show a claim  → formatted details
        │
        ▼
convert_claims ──> existing converter.py + mir_generator.py
                   produce the fixed-width .mir records
        │
        ▼
file verified + saved under data/generated/<session>/
        │
        ▼
[ Download ] buttons  (GET /api/mir/download/{file_id})
return the ACTUAL generated .mir file (or a ZIP of several)
```

Key points:

- The raw 835 is parsed **once** on upload; only a small structured summary and
  tool results are ever sent to the model — never the whole file.
- Claim IDs, amounts, dates and names always come from the parsed 835, so the
  AI cannot invent them.
- "MIR generated successfully" is only reported after the file was actually
  written and verified on disk.
- Everything stays local: Ollama + Llama 3.2, no cloud AI, no external servers.

### All commands (manual setup & run)

Prefer clicking `setup.bat` / `start.bat`? You can skip this section. These are
the exact commands those scripts run, if you want to do it by hand.

**1. Install prerequisites**

- **Python 3.12** — https://www.python.org/downloads/ (tick *"Add python.exe to PATH"*)
- **Node.js LTS** — https://nodejs.org/
- **Ollama** — https://ollama.com

**2. Ollama + Llama 3.2 model (once)**

```powershell
ollama pull llama3.2
ollama list              # confirm "llama3.2" appears
```

**3. Python backend (once, from the project folder)**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**4. Frontend (once)**

```powershell
pushd frontend
npm install
npm run build            # optional; creates frontend/dist served by the backend
popd
```

**5. Run (two terminals)**

Terminal A — backend:

```powershell
.venv\Scripts\activate
python -m uvicorn webapp:app --host 127.0.0.1 --port 8000
```

Terminal B — frontend dev server (proxies `/api` to `:8000`):

```powershell
cd frontend
npm run dev
```

Open **http://localhost:5173**.

**6. Stop** — press `Ctrl+C` in both terminals.

**7. Run the tests**

```powershell
.venv\Scripts\activate
python -m pytest tests -q
```

**Other entry points**

| What                                  | Command / file                          |
| ------------------------------------- | --------------------------------------- |
| One-click start (backend+frontend+browser) | `start.bat`                        |
| One-time full setup                    | `setup.bat`                             |
| Terminal-only agentic assistant        | `python main.py` (or `run-agent.bat`)   |
| Old single-page converter UI           | `run.bat` → http://127.0.0.1:8000       |
| Plain CLI conversion                   | `python cli.py input\sample_payment.835 -o out.mir` |

### Troubleshooting

- **"Frontend dependencies not found"** — `frontend\node_modules` is missing.
  `setup.bat` and `start.bat` now install it automatically, but if it still
  fails, run it manually and read the error output:
  ```
  cd frontend
  npm install
  ```
- **`npm install` fails / times out** — usually a network or registry problem.
  Retry, or use a mirror registry:
  ```
  cd frontend
  npm install --registry https://registry.npmmirror.com
  ```
- **"Virtual environment not found"** — run `setup.bat`, or do it by hand:
  ```
  py -3.12 -m venv .venv
  .venv\Scripts\activate
  pip install -r requirements.txt
  ```
- **"Ollama is not running"** — start the Ollama app (or `ollama serve`) and make
  sure the model is present: `ollama pull llama3.2`.
- **Ports 5173 / 8000 already in use** — close the other program using them, or
  change the ports in `frontend/vite.config.js` and in the `start.ps1` backend
  command.

### Sharing this project with another person

Zip the project folder **excluding** the machine-specific / generated folders.
They contain absolute paths for your PC and would break on another machine:

Excluded when zipping:

- `.venv`                  — recreated by `setup.bat`
- `frontend/node_modules`  — recreated by `setup.bat`
- `__pycache__`, `.pytest_cache`
- `logs`, `data`, `output`, `generated`

Keep everything else, especially `input/sample_payment.835` (a ready test file),
all `.py` files, `frontend/`, `setup.bat` and `start.bat`.

The other person must install:

1. **Python 3.12** — https://www.python.org/downloads/ (tick *"Add python.exe to PATH"*)
2. **Node.js LTS** — https://nodejs.org/
3. **Ollama** — https://ollama.com , then pull the model:
   ```
   ollama pull llama3.2
   ```

Then:

```
setup.bat        (one time: creates .venv, installs deps, verifies Ollama/model)
start.bat        (starts Ollama, backend, frontend, opens the browser)
```

Everything runs locally on their PC at `http://localhost:5173`. If a required
tool is missing, the scripts print a clear message instead of failing silently.

## Agentic terminal assistant

```

Requirements: Python 3.12, [Ollama](https://ollama.com) installed, and the model pulled:

```
ollama pull llama3.2
```

Then run:

```
python main.py
```

Or double-click `run-agent.bat`. You will be asked for the path of a local 835 file, the file is parsed and analyzed, and a conversational session starts:

```
> Find Ashay's claim.
I found 2 matching claims:
1. 86520262053343501 — paid 87.50
2. 86520262053343502 — paid 400.00

> Generate MIR for the second one.
Where would you like me to save the generated MIR file?
> C:\MIR\ashay_claim.mir
MIR generated successfully. Saved to: C:\MIR\ashay_claim.mir
```

Supported capabilities:

- Greetings / general conversation
- File summary: `How many claims are there?`
- Search: `Find Ashay's claim.`
- Filter: `claims above 5000`
- Claim details: `Show me claim CLM12345.`
- MIR generation for one or many claims, with an interactive output-path
  prompt, directory creation, and overwrite confirmation (files are never
  silently overwritten)
- Context: "the second one" / "it" resolve against the last search/filter
  selection
- System commands: `/help  /status  /file  /clear  /exit` (or `bye`)

## Design principle

> The AI decides what to do; deterministic software does the actual data processing.

The Llama 3.2 agent only plans (which tool, what arguments). Every claim
search, amount, count, MIR record and file path is produced by deterministic
Python code, so the agent can never invent claims or claim it saved a file it
did not write. The raw 835 is never sent to the LLM — only a structured
analysis summary and small tool results.

## Agentic project layout

```
main.py                  entry point (startup, 835 load + analysis, chat)
chat.py                  terminal chat loop / banner
agent/
  state.py               session state (selection, output path, history)
  prompts.py             decision protocol + tool manifest
  ollama.py              local Ollama client (Llama 3.2)
  supervisor.py          intent → tool selection → orchestration
tools/
  analysis.py            835 analysis summary (session context)
  search_claims.py       search + filter over parsed claims
  claim_details.py       deterministic claim list/detail formatting
  conversion.py          MIR generation wrapper (reuses converter.py)
  validation.py          output-path validation
  file_manager.py        directory creation + verified file writing
```

Configuration for the agent lives in `config.py` (`OLLAMA_HOST`,
`OLLAMA_MODEL`, limits, directories).

## Web UI / CLI (existing converter)

- Upload an 835 through a local web UI.
- Parses CLP, NM1 QC/IL, REF 1L, DTM, SVC and CAS.
- Generates one MIR `MO` record per claim, splitting claims into additional records after 50 service lines.
- Populates fields confidently available/derivable from the 835.
- Preserves unavailable/API-sourced fields as fixed-width blanks or format defaults.
- Downloads the generated `.mir` file.
- Also includes a CLI for batch use.

## Important design rule

Business constants are centralized in `config.py` and fixed positions are centralized in `mir_layout.py`. Do not scatter business constants inside converter logic.

Future API-only fields belong in `api_enrichment.py`.

## Windows: easiest way to run

1. Install **Python 3.12** and make sure the Python launcher (`py`) is available.
2. Extract this ZIP.
3. Double-click `run.bat`.
4. Your browser opens at `http://127.0.0.1:8000`.
5. Upload the 835 and click **Generate MIR**.
6. Click **Download MIR**.

The first run installs the required Python packages into a local `.venv` folder.

## Run manually

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000`.

## CLI

```powershell
python cli.py "my835.x12" -o "output.mir"
```

## Central configuration

Edit `config.py` for constants such as:

- `MIR_RECORD_TYPE`
- `MIR_HEADER_LENGTH`
- `MIR_SERVICE_BLOCK_LENGTH`
- `MAX_SERVICE_LINES_PER_RECORD`
- `SERVICE_OVERFLOW_MODE` (`split` by the spreadsheet specification; `truncate` available if production confirms that behavior)
- `MEMBER_ID_LENGTH`
- defaults and amount formatting

Edit `mir_layout.py` if a fixed MIR start position or field length changes.

## Current mapping notes

Known direct/derived fields include claim number, claim reference, claim status, member ID, group number, patient name, DOB, service charge, paid amount, covered charge, patient liability, service count, PR1–PR10 payment-reduction slots, and claim splitting/sequence.

The two MIR header dates observed in the supplied reference MIR are intentionally blank because they do not match a reliable date source in the supplied 835. They can later be populated through `api_enrichment.py`.

## Validation status

This is a working **v1 converter**, not yet a production certification. It is validated against the supplied 835/MIR pair for the mapped fields and fixed record lengths. Before replacing a production MIR feed, validate another known-good 835/MIR pair and connect the missing API-sourced fields.
