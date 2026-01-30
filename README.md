# Multi-Agent Interview Coach (CrewAI)

Python 3.11+ multi-agent CLI для тренировки техинтервью. Интервьюер + Observer + Hiring Manager, orchestration CrewAI. Логи и финальный отчёт в структурированном JSON.

## Setup (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

Настройте ключ LLM (OpenAI, Anthropic или OpenRouter) для реальных ответов:
```powershell
$env:OPENAI_API_KEY="sk-..."
# optional:
$env:MODEL_NAME="gpt-4o-mini"

# Tavily (приоритетный веб-поиск):
$env:TAVILY_API_KEY="tvly-..."

# OpenRouter (OpenAI-compatible):
$env:OPENROUTER_API_KEY="sk-or-..."
$env:OPENROUTER_MODEL="openrouter/auto"
$env:OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
# Для надёжности CrewAI берёт их как OPENAI_API_KEY/OPENAI_BASE_URL:
$env:OPENAI_API_KEY=$env:OPENROUTER_API_KEY
$env:OPENAI_BASE_URL=$env:OPENROUTER_BASE_URL
```
Без ключей работает детерминированный mock.

## Run interactive interview
```powershell
python -m interview_coach.main --name "Иван" --position "Backend" --grade "Middle" --experience "3 года"
# или просто:
python -m interview_coach.main
```
Команды управления: `Стоп интервью`, `Стоп игра`, `Давай фидбэк`, `stop`, `/stop`.
Команда прогресса: `Прогресс` — покажет краткую сводку покрытия тем (must/overall, covered/in progress).

## Run scripted scenario
```powershell
python -m interview_coach.scenario_runner scenarios/example_secret_scenario.json
```

## Logs
- Сохраняются в `logs/interview_log_YYYYMMDD_HHMMSS.json`
- Формат:
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

## Topic plan & coverage tracking
- На старте строится TopicPlan по позиции/грейду/опыту (каталог тем в `src/interview_coach/topic_catalog.py`).
- Каждый ход выбирается тема (приоритет must, учёт покрытия и средних баллов); Interviewer получает фиксированный topic_id.
- internal_thoughts логирует выбранную тему и метрики покрытия.
- Финальный отчёт включает Coverage-блок: must/overall %, covered/not covered.
- Команда `Прогресс` выводит текущий coverage.

## Tests
```powershell
pytest
```
