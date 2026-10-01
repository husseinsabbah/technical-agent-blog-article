# Technical Blog Agent

A local multi-agent blog-writing workflow built with Google ADK and Gemini. The current version is focused on technical articles for software engineers.

## What it does

1. `blog_planner` creates a Markdown outline and stores it as `blog_outline`.
2. `blog_writer` writes the article from that outline and stores it as `blog_post`.
3. `blog_reviewer` checks structure, code-example consistency, and likely issues, then stores its report as `quality_review`.

The reviewer is another language-model pass, not a source-backed fact checker. It does not browse the Web or execute code, so verify factual claims and examples before publishing.

## Requirements

- Python 3.10 or newer
- A Gemini API key from Google AI Studio
- Google ADK for Python and Streamlit

Install the dependencies from the repository root:

```powershell
py -m pip install -r requirements.txt
```

## Configure

Copy `blog_agent/.env.example` to `blog_agent/.env`, then put your key in the new file:

```dotenv
GOOGLE_API_KEY=your_key_here
```

Never commit `.env` or share its contents. The root `.gitignore` excludes `.env` files and ADK local state. If a key is exposed, revoke it and create a replacement.

The model is configured by `MODEL` in `blog_agent/agent.py`.

## Run locally

From the repository root, start the local Streamlit app:

```powershell
py -m streamlit run streamlit_app.py
```

The app opens at `http://localhost:8501`. Enter a technical topic to get the outline, article, and reviewer report. Each generation makes three model requests. The session keeps up to 20 results in memory, lets you select a past result, and can download an article as Markdown. This history is temporary and is lost when the browser tab or server session ends.

The ADK development UI is also available when debugging the underlying agents:

```powershell
adk web --port 8000
```

Open `http://127.0.0.1:8000` and select `blog_agent`. ADK Web is for local development and debugging, not production hosting.

To use the interactive terminal instead:

```powershell
adk run blog_agent
```

If PowerShell cannot find `adk`, reopen the terminal after installation or run `adk.exe` from Python's Scripts directory. On this machine, that directory can be printed with:

```powershell
py -c "import sysconfig; print(sysconfig.get_path('scripts'))"
```

## Tests

The unit tests check workflow order, shared state keys, model configuration, and the writer's transient-server-error retry configuration. They do not make Gemini API calls:

```powershell
py -m unittest discover -s tests -v
```

The Streamlit UI test also runs headlessly and does not call Gemini.

## Quota and retries

One successful article uses three Gemini requests: planner, writer, and reviewer. The writer retries `ServerError` failures up to three attempts total; quota errors such as `429 RESOURCE_EXHAUSTED` are not retried. Check the model's quota before repeated tests.
