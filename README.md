# Interview Coach - multi-agent CLI для тренировки техинтервью

**Interview Coach** - CLI-симулятор технического интервью на базе CrewAI. Система моделирует интервьюера, наблюдателя и hiring manager, задает вопросы по плану тем, оценивает ответы, адаптирует сложность и формирует финальный отчет.

## Возможности
- Многоагентная архитектура: Interviewer, Observer, Hiring Manager.
- Динамический план тем и трекинг покрытия (must/overall).
- Адаптация сложности по ответам, грейду и опыту.
- Поддержка разных стеков: язык и фреймворк определяются по позиции/опыту.
- Контроль off-topic, prompt-injection, спорных утверждений.
- Логи интервью и финальный отчет в JSON.
- Режим сценариев (scripted) для автотестов и демо.
- Offline stub, если нет ключей к LLM.

## Архитектура

### Роли агентов
- **Interviewer** - ведет интервью, задает следующий вопрос и дает короткий комментарий.
- **Observer** - анализирует ответ, оценивает корректность и предлагает follow-up.
- **Hiring Manager** - формирует итоговый отчет и рекомендации.

### Поток выполнения (упрощенно)
```
Пользователь -> CLI (main.py)
  -> Observer: анализ ответа -> ObserverAnalysis
  -> Planner: формирует InterviewerPlan
  -> Interviewer: финальная фраза (реакция + вопрос)
  -> Progress: обновление покрытия тем и сложности
  -> Logger: сохранение шага
```

### Основные компоненты
- `main.py` - главный цикл интервью, выбор тем, обновление сложности, интеграция агентов.
- `crewai_setup.py` - создание агентов и задач CrewAI.
- `prompts.py` - системные промпты агентов.
- `topics.py` - построение плана тем и выбор следующей темы.
- `topic_catalog.py` - каталог тем по ролям/грейдам.
- `logic.py` - эвристики intent/off-topic/prompt-injection/спорных утверждений.
- `tooling.py` - web_search инструмент (Tavily -> DDG -> DDG API -> SearX -> StackOverflow).
- `schemas.py` - Pydantic схемы данных.
- `logger.py` - сохранение логов и финального отчета.

### Как учитывается грейд и опыт
- Стартовая сложность: Junior=2, Middle=3, Senior=4.
- Если в опыте >= 8 лет, сложность повышается на 1 (до максимума 5).
- Если в опыте <= 1 года, сложность понижается на 1.
- Для Senior есть стартовый сдвиг в сторону system design/конкурентности.

## Структура проекта
```
src/interview_coach/
  main.py              # CLI и главный цикл интервью
  prompts.py           # системные промпты
  crewai_setup.py      # агенты и задачи CrewAI
  topics.py            # план тем и выбор темы
  topic_catalog.py     # каталог тем
  logic.py             # эвристики intent/off-topic/prompt-injection
  schemas.py           # Pydantic модели
  tooling.py           # web_search инструмент
  config.py            # конфигурация LLM и offline stub
  logger.py            # логирование интервью
  resources.py         # ссылки на ресурсы для фидбэка
  scenario_runner.py   # запуск сценариев
```

## Установка
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

## Конфигурация
Без ключей включается детерминированный offline stub.

Основные переменные окружения:
- `OPENAI_API_KEY` - ключ OpenAI (или OpenRouter, если начинается с `sk-or-`).
- `ANTHROPIC_API_KEY` - ключ Anthropic.
- `MODEL_NAME` - модель (по умолчанию `gpt-4o-mini`).
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL` - параметры OpenRouter.
- `TAVILY_API_KEY` - Tavily (приоритетный web_search).
- `SEARX_URL` - SearXNG fallback.
- `MOCK_MODE=true` - принудительный offline stub.

Пример:
```powershell
$env:OPENAI_API_KEY="sk-..."
$env:MODEL_NAME="gpt-4o-mini"

$env:TAVILY_API_KEY="tvly-..."

$env:OPENROUTER_API_KEY="sk-or-..."
$env:OPENROUTER_MODEL="openrouter/auto"
$env:OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
$env:OPENAI_API_KEY=$env:OPENROUTER_API_KEY
$env:OPENAI_BASE_URL=$env:OPENROUTER_BASE_URL
```

## Запуск
### Интерактивно
```powershell
python -m interview_coach
```
или
```powershell
python -m interview_coach.main --name "Иван" --position "Backend" --grade "Middle" --experience "3 года"
```

Система обязательно собирает профиль кандидата: имя, позиция, грейд, опыт.

Команды во время интервью:
- `Стоп интервью`, `Стоп игра`, `Давай фидбэк`, `stop`, `/stop`
- `Прогресс` - сводка покрытия тем

### Сценарии
```powershell
python -m interview_coach.scenario_runner scenarios/example_secret_scenario.json
```

## Логи
Логи сохраняются в `logs/interview_log_YYYYMMDD_HHMMSS.json`.

Пример формата:
```json
{
  "participant_name": "...",
  "turns": [
    {
      "turn_id": 1,
      "agent_visible_message": "...",
      "user_message": "...",
      "internal_thoughts": "[Observer]: ..."
    }
  ],
  "final_feedback": { ... }
}
```

## Как формируются темы и стек
- Базовый каталог тем - `topic_catalog.py`.
- План зависит от грейда (Junior/Middle/Senior).
- Язык и фреймворк определяются из текста позиции/опыта и переименовывают темы
  (например, `Java basics`, `Spring / Framework basics`).

## Тесты
```powershell
pytest
```

## Как адаптировать под свой стек
1. Обновите `topic_catalog.py` для новых ролей/тем.
2. Добавьте ключевые слова языков/фреймворков в `topics.py`.
3. Настройте поведение агентов в `prompts.py`.

## Ограничения
- Эвристики intent/off-topic не идеальны.
- Глубина ответов зависит от LLM и правил в промпте.
- Для стабильного web_search лучше использовать `TAVILY_API_KEY`.
