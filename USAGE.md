# Руководство по использованию системы хранения документов

## 🚀 Быстрый старт

### 1. Запуск бота
```bash
# Локально
python3 bot/main.py

# В Docker
docker-compose up -d
```

### 2. Отправка документов
Просто отправьте документ (PDF, JPG, DOCX, XLSX, ZIP) в Telegram-бота. Система автоматически:
- Извлечёт текст
- Определит тип документа
- Извлечёт ключевые поля
- Сохранит в структурированную базу
- Создаст/обновит бизнес-цепочки

### 3. Получение отчётов
Используйте команды в Telegram-боте:

```
/report                    # Общий отчёт по всем контрагентам
/report ООО Контрагент     # Отчёт по конкретному контрагенту
/unclosed                 # Незакрытые бизнес-цепочки
/monthly 2024 12          # Месячный отчёт
/chain Д-2024-001         # Детали цепочки
```

## 📁 Структура хранения

Документы автоматически сохраняются по схеме:
```
data/documents/
├── договоры/
│   └── ООО Контрагент/
│       └── 20241201_143022_договор.pdf
├── счета/
├── акты/
├── накладные/
├── счет-фактуры/
├── упд/
├── выписки/
└── иные/
```

## 🗄️ База данных

SQLite база: `data/documents/documents.db`

### Таблицы:
- **documents** — все обработанные документы
- **counterparties** — контрагенты с статистикой
- **business_chains** — бизнес-цепочки
- **chain_links** — связи документов в цепочках

### Просмотр данных:
```bash
sqlite3 data/documents/documents.db
.tables                    # Список таблиц
SELECT * FROM documents;   # Все документы
SELECT * FROM business_chains;  # Бизнес-цепочки
```

## 📊 Экспорт отчётов

### Командная строка:
```bash
# Отчёт по контрагентам
python3 export_reports.py --type counterparties --format excel

# Незакрытые цепочки
python3 export_reports.py --type unclosed --format csv

# Месячный отчёт
python3 export_reports.py --type monthly --year 2024 --month 12

# С фильтрацией по контрагенту
python3 export_reports.py --type counterparties --counterparty "ООО Контрагент"
```

### Программно:
```python
from analytics import analytics

# Отчёт по контрагентам
report = analytics.generate_counterparty_report()
analytics.export_to_excel(report, "отчет.xlsx")

# Незакрытые цепочки
unclosed = analytics.generate_unclosed_chains_report()
analytics.export_to_csv(unclosed, "незакрытые")
```

## 🔗 Бизнес-цепочки

Система автоматически создаёт и отслеживает бизнес-цепочки:

**Договор** → **Счета** → **Закрывающие документы** (акты, накладные, УПД)

### Логика:
1. **Договор** создаёт новую цепочку
2. **Счета** добавляются к цепочке по номеру договора
3. **Закрывающие документы** уменьшают незакрытую сумму
4. Система отслеживает остатки и возраст цепочек

### Статусы цепочек:
- **active** — активная цепочка
- **closed** — полностью закрытая
- **overdue** — просроченная

## 🧪 Тестирование

Запустите тесты системы:
```bash
python3 test_storage.py
```

Тест создаст:
- Тестовые документы (договор, счёт, акт)
- Бизнес-цепочку
- Проверит отчёты и аналитику

## ⚙️ Настройка

### Переменные окружения:
```bash
TELEGRAM_TOKEN=your_bot_token
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=mistral
OUR_COMPANY="ООО Ваша Компания"
```

### Пути к данным:
- База данных: `data/documents/documents.db`
- Документы: `data/documents/{тип}/{контрагент}/`
- Отчёты: `reports/`

## 🔧 Устранение неполадок

### Проблемы с базой данных:
```bash
# Проверка структуры
sqlite3 data/documents/documents.db ".schema"

# Резервная копия
cp data/documents/documents.db backup_$(date +%Y%m%d).db
```

### Проблемы с отчётами:
```bash
# Проверка зависимостей
pip3 install pandas openpyxl

# Тест аналитики
python3 -c "from analytics import analytics; print('OK')"
```

### Очистка тестовых данных:
```bash
rm -rf data/documents/*
rm -rf reports/*
```

## 📈 Мониторинг

### Ключевые метрики:
- Количество документов в базе
- Количество незакрытых цепочек
- Общая незакрытая сумма
- Возраст старых цепочек (>90 дней)

### Команды для мониторинга:
```bash
# Количество документов
sqlite3 data/documents/documents.db "SELECT COUNT(*) FROM documents;"

# Незакрытые цепочки
sqlite3 data/documents/documents.db "SELECT COUNT(*) FROM business_chains WHERE total_amount > closed_amount;"

# Топ контрагентов
sqlite3 data/documents/documents.db "SELECT counterparty, SUM(amount) as total FROM documents GROUP BY counterparty ORDER BY total DESC LIMIT 5;"
``` 