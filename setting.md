# Пошаговая инструкция по запуску

## 1. Соберите необходимые данные
1. Получите OAuth-токен Donation Alerts с правами `oauth-user-show`, `oauth-donation-subscribe`, `oauth-donation-index`.
2. Выпишите свой числовой `DA_USER_ID` (виден в адресной строке кабинета Donation Alerts).
3. При необходимости автоматического обновления токена подготовьте `DA_CLIENT_ID` и `DA_CLIENT_SECRET`.

## 2. Создайте `.env` в корне проекта
Вставьте свои значения вместо заглушек:
```
DA_WS_URL=https://centrifugo.donationalerts.com/connection/websocket
DA_API_BASE=https://www.donationalerts.com/api/v1
DA_ACCESS_TOKEN="ВАШ_ТОКЕН"
DA_USER_ID=123456
LLM_ENDPOINT=http://127.0.0.1:11434/v1/chat/completions
LLM_MODEL_ID=qwen2.5:7b-instruct-Q4_K_M
LLM_BACKEND=ollama
SHOW_DURATION_SEC=90
```
> Файл `.env` не коммитить и никому не пересылать.

## 3. Установите системные пакеты (WSL Ubuntu 24.04)
```
sudo apt update
sudo apt install python3.11-dev python3.11-venv build-essential \
     libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev libsdl2-gfx-dev \
     libportmidi-dev libfreetype6-dev
```
Убедитесь, что WSLg включён — окно pygame будет отображаться в Windows.

## 4. Запустите локальный сервер LLM
Используем Ollama:
```bash
ollama pull qwen2.5:7b-instruct-Q4_K_M
ollama serve
```
Сервер по умолчанию слушает `127.0.0.1:11434`. Убедитесь, что эндпоинт отвечает:
```bash
curl http://127.0.0.1:11434/v1/models
ollama show qwen2.5:7b-instruct-Q4_K_M | grep quantization
```

## 5. Подготовьте Python-окружение
```
poetry install --with dev
source $(poetry env info --path)/bin/activate
```

## 6. Проверьте OAuth-токен
```
poetry run python -m httpx get "https://www.donationalerts.com/api/v1/user/oauth" \
  -H "Authorization: Bearer $DA_ACCESS_TOKEN"
```
В ответе должны быть поля профиля и `socket_connection_token`. Ошибка 401 означает неправильный токен или недостаточные права.

## 7. Запустите сервис
```
poetry run python -m draw_stream.main
```
Появится окно pygame (через WSLg). FastAPI панель доступна по `http://0.0.0.0:8080`.

## 8. Настройте OBS / Streamlabs
1. В Windows добавьте источник *Window Capture* и выберите окно pygame.
2. Настройте аудиоисточники и RTMP-потоки (Twitch, TikTok и т.д.).
3. Проверьте, что окно отображается без артефактов и FPS стабильный.

## 9. Управляйте очередью
- `GET /queue` — текущее состояние.
- `POST /queue/skip` — пропуск текущего рисунка.
- `POST /queue/clear` — очистка очереди (без остановки действующего рендера).
- Следите за логами (`llm.plan_failed` подскажет проблемы с генерацией).

## 10. Корректное завершение
- Нажмите `Ctrl+C` в терминале.
- Приложение завершит текущий рендер, разорвёт соединения и закроет pygame.

## Что сообщить коллегам при передаче проекта
- Свой `DA_USER_ID` и способы получения токена (при необходимости — собственное OAuth-приложение).
- Параметры LLM-сервера: endpoint, модель, тип квантизации.
- Пользовательские настройки рендера (масштаб окна, длительность показа и т.д.).

> Никогда не отправляйте токен в открытых чатах или репозитории. При необходимости выдавайте новые токены под каждого оператора.
