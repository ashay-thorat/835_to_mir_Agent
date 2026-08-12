# 835 → MIR Converter & AI Assistant

Convert healthcare **EDI 835** payment files into **MIR** records — using a plain-English
AI assistant that runs 100% on your own computer. No cloud, no API keys, no data leaving
your PC.

```
You upload a .835 file  ──►  an AI assistant understands your questions  ──►  download .mir files
```

---

## What is all this? (plain English)

- **835** is a standard electronic file that health insurers send to doctors/clinics to say
  *"this is how much we paid for each claim."* It looks like lines of text with `*` separators.
- **MIR** is a fixed-width record file (every line is a specific length) that a practice's
  billing/accounting system needs in order to import that payment information.
- **The AI assistant** is a chatbot powered by **Llama 3.2** (via **Ollama**). You ask
  questions in normal language — *"find Ashay's claim"* — and it finds the data for you, or
  generates the MIR files.
- **Important:** the AI never sees the whole 835. It only decides *what* to do. All searching,
  counting, and file generation is done by regular deterministic Python code, so it can never
  invent claims or amounts.

---

## What can you do with it?

| # | Feature | Best for | How to run |
|---|---------|----------|------------|
| 1 | **AI web app** (chatbot in your browser) | Most people | `start.bat` |
| 2 | **AI terminal assistant** (chat in the command line) | Developers, scripting | `run-agent.bat` |
| 3 | **Simple converter web page** (upload → download) | Quick single conversions | `run.bat` |
| 4 | **One-line CLI converter** | Batch / automation | `python cli.py ...` |

---

## Folder structure

```
835_to_mir_app/
├── main.py            # AI terminal assistant (entry point #2)
├── cli.py             # Command-line converter (entry point #4)
├── app.py             # Simple converter web app (entry point #3)
├── webapp.py          # AI web app backend (entry point #1)
├── converter.py       # Shared conversion API (835 → MIR)
├── edi835_parser.py   # Reads the 835 file into structured claims
├── mir_generator.py   # Builds the fixed-width MIR records
├── mir_mapper.py      # Maps 835 values into MIR fields
├── mir_layout.py      # MIR field positions / lengths
├── config.py          # All settings in one place
├── models.py          # Claim / service / adjustment data objects
├── api_enrichment.py  # Extra header fields derived from the 835
├── chat.py            # Terminal chat loop
├── agent/             # AI brain: Ollama client, prompts, supervisor, state
├── tools/             # Deterministic actions (search, filter, convert, save)
├── web/               # Web session handling (uploads, downloads, zips)
├── frontend/          # React web app (the browser UI)
├── tests/             # Automated tests
├── input/             # Sample 835 file for testing
├── setup.bat          # One-time installer (Windows)
├── start.bat          # Starts the AI web app (Windows)
├── run.bat            # Starts the simple converter (Windows)
└── run-agent.bat      # Starts the terminal assistant (Windows)
```

---

## Before you start (prerequisites)

You need these three things installed once. The Windows scripts will check for them.

| Program | Why | Download / verify |
|---------|-----|-------------------|
| **Python 3.12** | Runs the backend | https://www.python.org/downloads/ — tick **"Add python.exe to PATH"** |
| **Node.js LTS** | Builds the web app | https://nodejs.org/ |
| **Ollama** | Runs the local AI model | https://ollama.com |

Verify they are installed (open a command prompt / PowerShell):

```powershell
py --version        # should print Python 3.12.x
node --version      # should print v20 or newer
ollama --version    # should print a version number
```

Then pull the AI model once (this downloads ~2 GB, takes a few minutes):

```powershell
ollama pull llama3.2
```

> **Don't have all three?** That's fine — you can still use the **simple converter** (#3) and the
> **CLI** (#4), which only need Python.

---

## Quick start (Windows — easiest)

1. Install the prerequisites above.
2. Open this folder in File Explorer.
3. **First time only:** double-click `setup.bat` (creates `.venv`, installs Python + Node
   dependencies, builds the frontend, and makes sure Llama 3.2 is downloaded).
4. Double-click `start.bat` every time you want to use it.

Two new windows open (backend + frontend) and your browser opens at:

```
http://localhost:5173
```

That's the AI web app. Keep those windows open while you use it.

---

## Option 1 — Use the AI web app (recommended)

1. On the page, click **Upload 835 File** and pick a `.835` file.
2. The file is parsed and you see a claim count.
3. Start chatting. Try these examples:

| You type | The assistant does |
|----------|--------------------|
| `Hi` | Greets you |
| `How many claims are there?` | Shows a summary |
| `Find Ashay's claim.` | Searches patient names |
| `Which claim has the highest payment?` | Filters by amount |
| `Find claims above 5000.` | Filters by amount |
| `Show me the details of claim CLM12345.` | Shows full claim details |
| `Generate MIR for the second one.` | Generates one `.mir` file |
| `Generate MIR for all Ashay's claims.` | Generates files for all matches |
| `Convert the whole file into MIR.` | Generates one combined `.mir` file |

4. When MIR files are ready you get **Download** buttons (one per file), a **Download All (ZIP)**,
   and a **Combine into one file** option.

The top-right status bar shows whether **Backend**, **Ollama**, and **Llama 3.2** are online.

---

## Option 2 — Use the AI terminal assistant

Works without the browser — just a chat in your terminal.

```
run-agent.bat
```

(or, if you set up manually: `python main.py`)

1. It asks for the path of a 835 file, e.g. `input\sample_payment.835`.
2. It parses and analyzes the file, then shows an analysis report.
3. Chat with the same examples as the web app. It asks *where* to save generated MIR files.
4. System commands (start with `/`):

| Command | What it does |
|---------|--------------|
| `/help` | Shows help |
| `/status` | Shows file + model status |
| `/file` | Shows details of the loaded file |
| `/clear` | Clears the chat memory (file stays loaded) |
| `/exit` or `bye` | Exits |

---

## Option 3 — Simple converter web page

No AI needed — upload an 835, get a MIR back.

```
run.bat
```

Browser opens at `http://127.0.0.1:8000`. Upload → **Generate MIR** → **Download MIR**.

---

## Option 4 — One-line CLI converter

```powershell
python cli.py "my_payment.835" -o "output.mir"
```

If you leave out `-o`, it writes the MIR next to the input with a `.mir` extension.

```
python cli.py input\sample_payment.835
```

It prints a short summary: number of claims, service lines, and MIR records generated.

---

## Manual setup from scratch (all commands)

Skip this if you used `setup.bat` — these are the exact commands the scripts run, so you can do
it by hand on any OS (the batch files are Windows-only).

**1. Create and activate the Python environment (once):**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**2. Install the frontend dependencies and build (once):**

```powershell
pushd frontend
npm install
npm run build
popd
```

**3. Make sure Ollama has the model (once):**

```powershell
ollama pull llama3.2
```

**4. Run the AI web app (two terminals):**

Terminal A — backend:

```powershell
.venv\Scripts\activate
python -m uvicorn webapp:app --host 127.0.0.1 --port 8000
```

Terminal B — frontend (dev server, proxies `/api` to the backend):

```powershell
cd frontend
npm run dev
```

Open **http://localhost:5173**. Stop everything with `Ctrl+C` in both terminals.

**5. Run the simple converter manually:**

```powershell
.venv\Scripts\activate
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**.

**6. Run the AI terminal assistant manually:**

```powershell
.venv\Scripts\activate
python main.py
```

---

## Run the tests

```powershell
.venv\Scripts\activate
python -m pytest tests -q
```

---

## API endpoints (for developers)

The web app talks to a FastAPI backend at `http://127.0.0.1:8000`.

| Method | Endpoint | What it does |
|--------|----------|--------------|
| `GET` | `/api/health` | Backend / Ollama / model status |
| `POST` | `/api/files/upload` | Upload a 835, creates a session |
| `POST` | `/api/chat` | Send a chat message to the assistant |
| `POST` | `/api/convert/835-to-mir` | Convert the whole uploaded file |
| `GET` | `/api/mir/download/{file_id}` | Download a generated file |
| `POST` | `/api/mir/zip` | Bundle generated files into a ZIP |
| `POST` | `/api/mir/combine` | Combine generated files into one MIR |

---

## How it works

```
Upload .835
    │
    ▼
edi835_parser.py  ── parses the file once into structured Claim objects
    │
    ▼
tools/analysis.py ── builds a summary (claim count, totals, payer)
    │
    ▼
You chat ──► agent/ (Llama 3.2) decides WHICH tool to call
              (it only plans; it never touches the raw file)
    │
    ▼
tools/ run the work deterministically:
   search_claims.py   "find Ashay"       → matching claims
   filter_claims.py   "claims above 5000" → matching claims
   claim_details.py   "show claim"       → formatted details
    │
    ▼
convert_claims ──► converter.py + mir_generator.py build fixed-width .mir records
    │
    ▼
File written to disk + verified ──► Download buttons appear
```

Design principle: **the AI decides *what* to do; deterministic Python does the work.**
The raw 835 is never sent to the model — only a small structured summary.

---

## Configuration

Everything you might want to change lives in **`config.py`**:

- `OLLAMA_MODEL` — the local AI model (default `llama3.2`)
- `MIR_HEADER_LENGTH`, `MIR_SERVICE_BLOCK_LENGTH` — fixed record sizes
- `MAX_SERVICE_LINES_PER_RECORD` — claims split into extra records after this many lines
- `MEMBER_ID_LENGTH`, field lengths, amount formatting
- `APP_HOST` / `APP_PORT` — server address and port

MIR field positions and lengths live in **`mir_layout.py`**. Business rules stay out of the
converter logic so a format change is one edit in one file.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Python launcher py was not found" | Install Python 3.12 and tick "Add python.exe to PATH" |
| "Node.js was not found" | Install Node.js LTS from https://nodejs.org/ |
| "Ollama was not found" / "Ollama is not running" | Install https://ollama.com, start the Ollama app, then `ollama pull llama3.2` |
| "Frontend dependencies not found" | `cd frontend` then `npm install` |
| `npm install` fails / times out | Network/registry issue — retry, or use a mirror: `npm install --registry https://registry.npmmirror.com` |
| Port 5173 or 8000 already in use | Close the other program, or change ports in `frontend/vite.config.js` and `config.py` |
| "No 835 structure detected" | The file isn't a valid 835, or has no `CLP` segments |

---

## Privacy

Everything runs **locally** on your machine:

- The AI model (Llama 3.2) runs through Ollama on `127.0.0.1:11434` — no cloud AI.
- Uploaded 835s and generated MIRs stay on your PC under `data/`.
- If Ollama is down, the UI tells you to start it — it never silently falls back to a cloud API.

---

## Notes for developers

- Add tests under `tests/` and run `python -m pytest tests -q`.
- Keep business constants in `config.py` and fixed positions in `mir_layout.py`.
- Future API-sourced header fields go in `api_enrichment.py`.
- `make_zip.ps1` builds a clean shareable ZIP of the project (excludes `.venv`, `node_modules`,
  runtime data). Run: `powershell -ExecutionPolicy Bypass -File make_zip.ps1`

---

*Validated against the supplied 835/MIR sample pair. Before replacing a production MIR feed,
validate against another known-good 835/MIR pair and connect the missing API-sourced fields.*
