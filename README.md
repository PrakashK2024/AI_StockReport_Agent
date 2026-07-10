# 📈 AI Stock Research Agent

A Streamlit app that takes a ticker symbol or company name, pulls SEC filings and financial data, fetches price history, and uses Groq to generate a concise research brief.

## ✨ Features

- 🔎 Search by ticker symbol or company name
- 🏛️ Pull recent SEC filings and company facts
- 📊 Show price history and simple performance stats
- 🤖 Generate an AI-written research report with Groq
- 🎨 Clean Streamlit dashboard UI

## 🧱 Project structure

```text
.
├── App.py
├── agent.py
├── Stock_Agent.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## ✅ Requirements

- Python 3.10 or newer
- A Groq API key
- Internet access for SEC and Yahoo Finance requests

## 🚀 Setup

### 1) Clone the repository

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
```

### 2) Create a virtual environment

macOS and Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Set up your API keys and environment variables

Create a file named `.env` in the project root.
You can copy the example file first:

```bash
cp .env.example .env
```

Then open `.env` and fill in your values.

## 🔑 Groq API key setup

1. Create or log in to your Groq account.
2. Open the Groq API Keys page and generate a new key. Groq’s docs recommend setting the key as an environment variable, and their quickstart uses `GROQ_API_KEY`. 
3. Paste the key into your `.env` file.
4. Do **not** commit your real API key to GitHub.

Example:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
SEC_USER_AGENT=Your Name your.email@example.com
```

## 🧪 Environment variables

- `GROQ_API_KEY`, required, used for the planner and the final report
- `GROQ_MODEL`, optional, defaults to `llama-3.3-70b-versatile`
- `SEC_USER_AGENT`, recommended, used to identify your app to the SEC APIs

Groq’s docs also show the API being called through the OpenAI-compatible Groq base URL `https://api.groq.com/openai/v1`. citeturn134148search3turn134148search13

## ▶️ Run the app

```bash
streamlit run App.py
```

Then open the local URL shown in your terminal, usually:

```text
http://localhost:8501
```

## 🧭 How to use it

1. Type a ticker like `NVDA` or a company name like `NVIDIA`.
2. Click **Run research**.
3. The app will:
   - plan the research flow with Groq,
   - resolve the company through SEC data,
   - fetch filings, financial facts, and price history,
   - generate a Markdown research summary.
4. Review the report, metrics, filings, and chart in the dashboard.

## 💡 Example inputs

- `NVDA`
- `NVIDIA`
- `AAPL`
- `Apple`
- `MSFT`
- `Microsoft`

## 🛡️ Important notes

- This project is for research and educational use only.
- It does not provide financial advice.
- SEC requests can be rate-limited, so a proper `SEC_USER_AGENT` matters.
- Some symbols may have incomplete price or filing data depending on external sources.
- Keep `.env` private and leave it out of GitHub.

## 🧯 Troubleshooting

### `GROQ_API_KEY is missing`
Make sure your `.env` file exists and contains a valid Groq API key.

### `Could not resolve 'XYZ' to a SEC ticker`
Try a valid ticker symbol or a clearer company name.

### SEC request errors
Check that `SEC_USER_AGENT` is set and that you have internet access.

### Empty price chart or missing history
The app uses `yfinance` as a fallback source, so some symbols may have limited or delayed history.

## 🌱 Extending the project

Possible next improvements:

- Add side-by-side comparison output for two companies
- Cache SEC and price requests
- Add sentiment or news summarization
- Export reports to PDF or Markdown
- Add Docker support for easier deployment

## 📄 License

Add a license before publishing the repository if you want others to reuse the code freely.
