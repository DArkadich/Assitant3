# Telegram Документооборотчик (MVP)

## Быстрый старт

1. Скопируйте `.env.example` в `.env` и укажите свой Telegram BOT_TOKEN
2. Соберите и запустите контейнер:

```bash
docker build -t docbot .
docker run --env-file .env -v $(pwd)/data:/app/data -v $(pwd)/database:/app/database docbot
```

## Структура проекта

- `bot/` — код бота
- `models/` — модели данных
- `data/Документы/` — хранилище документов
- `database/db.sqlite3` — база данных

## Переменные окружения
- `BOT_TOKEN` — токен Telegram-бота
- `DATABASE_PATH` — путь к базе данных
- `DOCUMENTS_PATH` — путь к папке с документами 