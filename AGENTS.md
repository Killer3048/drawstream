ГЛАВНОЕ: Тебе доступен доступ в сеть, а также установка команд через pip. Доступны все sudo команды и выход из окружения.
ВАЖНО: Любая документация указанная ниже должна быть проверена и прочитана через curl.
ОКРУЖЕНИЕ: /home/vem/.cache/pypoetry/virtualenvs/draw-stream-b8xfp3zP-py3.11/bin/activate(draw-stream-py3.11)

# ТЗ: Интерактивный пайплайн пиксель‑арта по донатам (WSL2 + локальный mistral-nemo:12b-instruct-2407-q4_K_M)

## Кратко
Сервис принимает донаты (Donation Alerts), по каждому донату строит план рисования через локальную LLM **mistral-nemo:12b-instruct-2407-q4_K_M** (квант, оффлайн), анимированно отрисовывает пиксель‑арт в едином окне, показывает результат ~90 секунд с подписью **“All for you”**, ведёт FIFO‑очередь и оверлей очереди. Окно захватывается в OBS/Streamlabs на Windows и транслируется на Twitch и TikTok.

---

## Цели
- Реакция на входящие сообщения донатов во время эфира.
- Безопасность контента: 18+ запросы заменяются на текст **“You are too small”** (без рисунка).
- Детерминированный рендер через простую **Canvas‑DSL** (JSON): примитивы и шаги анимации.
- Одна актёрная «кисть» (строгий FIFO): пока идёт анимация/показ — следующие заявки только в очереди.
- Понятный HUD: текущая заявка, «Next up», таймер, подпись **“All for you”**.

---

## Архитектура (высокоуровнево)
- **Donation Ingestor** → получает события Donation Alerts (WS / REST) → нормализует → кладёт в очередь.
- **Gatekeeper** → быстрый NSFW‑фильтр (правила RU/EN). Если NSFW → задача `render_text: "You are too small"`.
- **LLM Orchestrator (Qwen)** → из запроса выдаёт **Canvas‑DSL (JSON)** без пояснений.
- **Renderer (pygame)** → интерпретирует DSL → **анимирует шаги рисования** → upscale до окна → рисует HUD и очередь.
- **Main Loop** → один воркер: берёт из FIFO, ждёт окончания рендера и показа (~90 сек), затем берёт следующую.

**Окружение:** WSL2 Ubuntu 24.04; окно pygame отображается в Windows через WSLg и захватывается в OBS.

---

## Компоненты
- **Сбор событий донатов:** Donation Alerts WebSocket (Centrifugo) или резервный REST‑поллинг.  
  Документация: [Donation Alerts API](https://www.donationalerts.com/apidoc). Неофициальное описание Centrifugo‑каналов: [DonationAlertsCentrifugoApi (3rd‑party)](https://stimulcross.github.io/donation-alerts/classes/api.DonationAlertsCentrifugoApi.html).
- **Очередь:** `asyncio.Queue` (строгий FIFO, конкурентность рендера = 1). Док: [asyncio.Queue](https://docs.python.org/3/library/asyncio-queue.html).
- **LLM (локально):** Qwen 2.5 7B Instruct.  
  Модельная карточка: [HF: Qwen/Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) • GGUF кванты (офиц.): [Qwen/Qwen2.5-7B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF).
  Бэкенды на выбор:
  - **llama.cpp** (OpenAI‑совместимый сервер): [GitHub](https://github.com/ggml-org/llama.cpp) • [llama-cpp‑python server](https://llama-cpp-python.readthedocs.io/en/latest/server/)
  - **vLLM** (OpenAI совместимый): [docs vLLM](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html)
  - **Hugging Face TGI**: [docs](https://huggingface.co/docs/text-generation-inference/en/index) • [GitHub](https://github.com/huggingface/text-generation-inference)
- **Веб/сеть:** `httpx` (LLM/REST), `websockets` (DA/панель). Док: [HTTPX](https://www.python-httpx.org/), [HTTPX Async](https://www.python-httpx.org/async/), [websockets](https://websockets.readthedocs.io/).
- **API/панель состояния:** `FastAPI` (health, skip/clear queue). Док: [FastAPI](https://fastapi.tiangolo.com/).
- **Валидация схемы:** `pydantic v2`. Док: [Pydantic v2](https://docs.pydantic.dev/latest/).
- **Рендер/GUI:** `pygame` + WSLg. Док: [pygame.draw](https://www.pygame.org/docs/ref/draw.html), [pygame.transform](https://www.pygame.org/docs/ref/transform.html), [pygame docs](https://www.pygame.org/docs/). WSLg: [Run Linux GUI apps with WSL](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps), [WSLg GitHub](https://github.com/microsoft/wslg).

---

## Функциональные требования

### 1) Инжест донатов
- Поддержать **WebSocket‑подписку** к приватным каналам Donation Alerts (Centrifugo) с OAuth‑авторизацией (получение токена, подписка на канал донатов пользователя). Ссылки: [Donation Alerts API](https://www.donationalerts.com/apidoc). Если WS недоступен, **резерв**: периодический REST‑поллинг списка донатов.
- Нормализовать событие: `id`, `donor`, `message`, `amount`, `currency`, `timestamp`.
- Логировать событие и класть в FIFO‑очередь.

### 2) Очередь (FIFO)
- Один воркер. Пока выполняется рендер и/или **показ результата ~90 сек**, следующие элементы не стартуют.
- HUD всегда показывает текущее задание и первые 3–5 элементов очереди («Next up»).

### 3) Gatekeeper (NSFW/18+)
- Слой правил/лексикона RU/EN (регексы, ключевые слова).
- При срабатывании → формируется задача: **`render_text: "You are too small"`** (без вызова рисовального промпта).

### 4) LLM Orchestrator (Qwen)
- Роль: из произвольной фразы доната вернуть **строгий JSON** по схеме Canvas‑DSL **без пояснений**.
- Температура невысокая (детерминизм), лимиты токенов — умеренные (задачи короткие).

### 5) Canvas‑DSL (JSON)
**Назначение:** декларировать финальный рисунок и **порядок/параметры анимации рисования**, чтобы рендер был детерминирован и лёгкий.

**Требования к схеме (верхний уровень):**
- `version`: строка версии DSL.
- `canvas`: объект с полями `w`, `h`, `bg` (например, 96×96, фон по умолчанию тёмно‑серый).
- `palette` *(опц.)*: ограниченная палитра hex‑цветов для пиксель‑вида.
- `steps`: массив **шагов рисования** (выполняются последовательно).
- `caption`: строка (всегда “All for you” для показа результата).
- `seed` *(опц.)*: число для детерминизма процедурных эффектов.
- Спец‑случай: вместо `steps` возможен объект `{ "render_text": "You are too small", "duration_sec": 90 }` для NSFW.

**Поддерживаемые операции в `steps`:**
- `rect` (x, y, w, h, fill?, outline?)
- `circle` (cx, cy, r, fill?, outline?)
- `line` (x1, y1, x2, y2, width)
- `polygon` (points[], fill?, outline?)
- `pixels` (points[] или матрица), `color`
- `text` (x, y, value, font?, size?, color?) — моно/ограниченно
- `group` (steps[]) — логическая группировка

**Анимация на уровне шага (`animate`):**
- Поле `animate` опционально, объект с параметрами:
  - `mode`: `"stroke"` | `"fill"` | `"pixel_reveal"`
  - `speed_px_per_s` *(для пиксельного раскрытия/линий)*
  - `duration_ms` *(жёсткая длительность шага)*
  - `delay_ms` *(задержка перед стартом шага)*
  - `ease`: `"linear"` | `"ease_in_out"` (базовые кривые)
- Если `animate` отсутствует — применяется дефолтная продолжительность из конфига.

**Размер холста и апскейл:**
- Базовый холст **96×96**. Масштабирование в видимое окно nearest‑neighbor (например, ×8 → 768×768) без сглаживания.

### 6) Рендерер и анимация
- Технология: **pygame**. Рисование на off‑screen Surface 96×96 → апскейл в основные координаты окна (nearest‑neighbor).
- Поддержать 60 FPS для простых сцен; при нехватке ресурсов допустима деградация до 30 FPS без разрывов анимации.
- Реализация режимов анимации:
  - **stroke**: обводка фигуры по периметру во времени.
  - **fill**: заполнение (радиально/построчно — решение за исполнителем; важна стабильность).
  - **pixel_reveal**: порционное открытие точек (`pixels`) по скорости.
- Обработка событий окна (quit и пр.) без блокировок event‑loop.
- **HUD**: зона очереди, «Drawing: …», прогресс‑бар/таймер показа результата, подпись **“All for you”**.

### 7) Показ результата
- После завершения всех шагов анимации держать финальный кадр около **90 секунд**. Тайминг конфигурируемый.
- В это время новые заявки только копятся в очереди (не стартуют).

### 8) Локальная панель (опционально)
- **FastAPI**: health‑эндпоинт, команды оператору (skip текущей, очистить очередь), облегчённые WS‑нотификации статуса.  
  Док: [FastAPI](https://fastapi.tiangolo.com/), [WebSockets в FastAPI](https://fastapi.tiangolo.com/advanced/websockets/).

---

## Нефункциональные требования

### Конфигурация (через переменные окружения)
- Donation Alerts: `DA_WS_URL`, `DA_API_TOKEN` / параметры OAuth, идентификатор пользователя/канала.
- LLM: `LLM_BACKEND` (`llamacpp` | `vllm` | `tgi`), `MODEL_ID`/путь к GGUF, `ENDPOINT`, `TEMPERATURE`, `MAX_TOKENS`.
- Renderer: `CANVAS_W`, `CANVAS_H`, `WINDOW_SCALE`, `DEFAULT_STEP_DURATION_MS`, `SHOW_DURATION_SEC`.
- Логи/уровни, локаль вывода HUD (английский).

### Зависимости (основные)
- Python 3.11, `pygame`, `httpx`, `websockets`, `fastapi`, `pydantic v2`, `dotenv` и др.  
  Док: [pygame](https://www.pygame.org/docs/), [HTTPX](https://www.python-httpx.org/), [websockets](https://websockets.readthedocs.io/), [FastAPI](https://fastapi.tiangolo.com/), [Pydantic v2](https://docs.pydantic.dev/latest/).

### Производительность и ресурсы
- Цель по LLM: короткие запросы → быстрая генерация JSON‑плана. На слабом CPU‑кванте возможны задержки; предусмотреть таймауты/ретраи HTTP‑клиента (`httpx`) и оповещение оператора.
- GGUF‑кванты для 7B: ориентироваться на карточку модели и инструкции по llama.cpp; выбирать Q4/Q5 по ресурсам.
- Renderer не блокирует event‑loop; долгие операции выполняются кооперативно.

### Логирование и устойчивость
- Структурные логи: приём доната, решение Gatekeeper, промпт‑латентность, длина очереди, FPS, исключения.
- Ретрай‑политики: переподключение к WS, повторы запросов к LLM‑серверу, безопасная обработка «почти JSON» (если парсинг не удался — показывать `render_text` и писать в лог причину).
- Грациозное завершение: закрытие WS/HTTP‑клиентов, остановка между задачами.

### Безопасность/приватность
- Не логировать токены и персональные данные доноров в открытом виде.
- Ограничить внешние сетевые вызовы только на необходимые хосты LLM/DA.

---

## Развёртывание и запуск (WSL2, без примеров кода)
- Установить WSL2 Ubuntu 24.04 на Windows 11; включить **WSLg** для GUI‑приложений Linux.  
  Ссылки: [WSL GUI‑приложения](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps), [WSLg GitHub](https://github.com/microsoft/wslg).
- Установить зависимости Python и системные пакеты для `pygame`.
- Выбрать бэкенд LLM и загрузить веса:
  - **llama.cpp** + **GGUF** (Qwen 2.5 7B Instruct): [Qwen GGUF](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF), [llama.cpp](https://github.com/ggml-org/llama.cpp), [llama‑cpp‑python server](https://llama-cpp-python.readthedocs.io/en/latest/server/).
  - или **vLLM**: [docs](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html).
  - или **TGI**: [docs](https://huggingface.co/docs/text-generation-inference/en/index).
- Заполнить переменные окружения для Donation Alerts и LLM.
- Запустить сервис; убедиться, что окно pygame появилось в Windows (через WSLg).

---

## Потоковое вещание (Windows, ознакомительно)
- **OBS Studio**: установить и настроить, добавить **Window Capture** для окна pygame.  
  Ссылки: [OBS Quick Start](https://obsproject.com/kb/quick-start-guide), [OBS Overview](https://obsproject.com/kb/obs-studio-overview), [OBS Knowledge Base](https://obsproject.com/kb/category/1).
- **Twitch**: базовые инструкции и курсы — [Twitch Creator Camp](https://www.twitch.tv/creatorcamp/), FAQ — [How do I stream?](https://help.twitch.tv/s/article/how-do-i-stream-faq?language=en_US).
- **TikTok (RTMP/Producer)**: доступ к стрим‑ключу у аккаунтов с включённым Live Producer; UI/правила меняются, официальной публичной документации мало. Практические руководства (3rd‑party):  
  [Restream: find TikTok stream key](https://restream.io/learn/platforms/how-to-find-tiktok-stream-key/),  
  [OneStream: TikTok stream key guide](https://onestream.live/blog/tiktok-stream-key-guide/),  
  [Castr: how to get a TikTok stream key](https://castr.com/blog/how-to-get-a-tiktok-stream-key/).  
  Общая справка по RTMP: [Riverside RTMP guide](https://riverside.com/blog/rtmp-streaming).

---

## Справочные ссылки (сводно)
- Donation Alerts API: https://www.donationalerts.com/apidoc  
- Qwen 2.5 7B Instruct: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct  
- Qwen GGUF (официальные): https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF  
- llama.cpp: https://github.com/ggml-org/llama.cpp  
- llama‑cpp‑python (OpenAI‑совм. сервер): https://llama-cpp-python.readthedocs.io/en/latest/server/  
- vLLM (OpenAI‑совм. сервер): https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html  
- Hugging Face TGI: https://huggingface.co/docs/text-generation-inference/en/index  
- FastAPI: https://fastapi.tiangolo.com/  
- Pydantic v2: https://docs.pydantic.dev/latest/  
- HTTPX: https://www.python-httpx.org/  
- websockets: https://websockets.readthedocs.io/  
- pygame docs: https://www.pygame.org/docs/  
- WSLg (GUI apps): https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps  
- OBS Quick Start: https://obsproject.com/kb/quick-start-guide  
- Twitch Creator Camp: https://www.twitch.tv/creatorcamp/  
- Restream TikTok stream key (3rd‑party): https://restream.io/learn/platforms/how-to-find-tiktok-stream-key/

---

## Заметки по границам
- Не входит: настройка аккаунтов/ключей платформ, аудио‑миксы, чат‑боты, расширенная модерация.
- Все подписи/надписи в трансляции — **на английском** (например, “All for you”, “Queue”, “Drawing: …”).

