# Multi-Agent Interview Coach (CrewAI)

Python 3.11+ multi-agent CLI for technical interview practice. Uses Interviewer + Observer + Hiring Manager agents orchestrated by CrewAI. Saves structured logs and final feedback.

## Setup (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

Set an LLM key (OpenAI, Anthropic, or OpenRouter) for real runs:
```powershell
$env:OPENAI_API_KEY="sk-..."
# optional:
$env:MODEL_NAME="gpt-4o-mini"

# OpenRouter option (OpenAI-compatible):
$env:OPENROUTER_API_KEY="sk-or-..."
$env:OPENROUTER_MODEL="openrouter/auto"   # pick any OpenRouter model id
$env:OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"  # default
# для надёжности CrewAI берёт эти env как OPENAI_API_KEY/OPENAI_BASE_URL:
$env:OPENAI_API_KEY=$env:OPENROUTER_API_KEY
$env:OPENAI_BASE_URL=$env:OPENROUTER_BASE_URL
```
Without keys the app runs in deterministic mock mode.

## Run interactive interview
```powershell
python -m interview_coach.main --name "Иван" --position "Backend" --grade "Middle" --experience "3 года"
# или просто:
python -m interview_coach.main
```
Stop commands: `Стоп интервью`, `Стоп игра`, `Давай фидбэк`, `stop`, `/stop`.

## Run scripted scenario
```powershell
python -m interview_coach.scenario_runner scenarios/example_secret_scenario.json
```

## Logs
- Saved to `logs/interview_log_YYYYMMDD_HHMMSS.json`
- Required shape:
```json
{
  "participant_name": "...",
  "turns": [
    {
      "turn_id": 1,
      "agent_visible_message": "...",
      "user_message": "...",
      "internal_thoughts": "[Observer]: ... [Interviewer]: ..."
    }
  ],
  "final_feedback": {...}
}
```

## Tests
```powershell
pytest
```
