# Миграция с SQLite на PostgreSQL

## 🚀 Быстрый старт

### 1. Остановите текущие контейнеры
```bash
docker-compose down
```

### 2. Запустите новую конфигурацию с PostgreSQL
```bash
docker-compose up -d postgres
```

### 3. Дождитесь готовности PostgreSQL
```bash
docker-compose logs postgres
# Дождитесь сообщения "database system is ready to accept connections"
```

### 4. Мигрируйте данные (если есть)
```bash
# Установите зависимости для миграции
pip3 install psycopg2-binary

# Запустите миграцию
python3 migrate_to_postgres.py
```

### 5. Запустите все сервисы
```bash
docker-compose up -d
```

## 📊 Преимущества PostgreSQL

### Производительность
- **Быстрые запросы** — оптимизированные индексы и представления
- **Параллельная обработка** — поддержка множественных соединений
- **Кэширование** — встроенный кэш запросов

### Надёжность
- **ACID транзакции** — гарантия целостности данных
- **Автоматические бэкапы** — через Docker volumes
- **Восстановление** — в случае сбоев

### Масштабируемость
- **Большие объёмы данных** — эффективная работа с миллионами записей
- **Сложные запросы** — поддержка оконных функций и CTE
- **Репликация** — возможность настройки master-slave

## 🔧 Настройка

### Переменные окружения
```bash
# В .env файле
DATABASE_URL=postgresql://doc_user:doc_password@postgres:5432/doc_checker
POSTGRES_DB=doc_checker
POSTGRES_USER=doc_user
POSTGRES_PASSWORD=doc_password
```

### Подключение к базе
```bash
# Через Docker
docker exec -it doc_checker_postgres psql -U doc_user -d doc_checker

# Локально (если порт открыт)
psql -h localhost -p 5432 -U doc_user -d doc_checker
```

## 📈 Мониторинг

### Проверка состояния базы
```bash
# Статистика базы данных
docker exec -it doc_checker_postgres psql -U doc_user -d doc_checker -c "
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats 
WHERE schemaname = 'public'
ORDER BY tablename, attname;
"

# Размер таблиц
docker exec -it doc_checker_postgres psql -U doc_user -d doc_checker -c "
SELECT 
    table_name,
    pg_size_pretty(pg_total_relation_size(table_name)) as size
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY pg_total_relation_size(table_name) DESC;
"
```

### Бэкапы
```bash
# Создание бэкапа
docker exec -it doc_checker_postgres pg_dump -U doc_user doc_checker > backup_$(date +%Y%m%d).sql

# Восстановление из бэкапа
docker exec -i doc_checker_postgres psql -U doc_user doc_checker < backup_20241201.sql
```

## 🧪 Тестирование

### Проверка подключения
```bash
python3 test_postgres.py
```

### Проверка отчётов
```bash
# Экспорт отчётов
python3 export_reports.py --type counterparties --format excel
python3 export_reports.py --type unclosed --format csv
```

## 🔄 Откат к SQLite

Если нужно вернуться к SQLite:

### 1. Остановите PostgreSQL
```bash
docker-compose stop postgres
```

### 2. Восстановите SQLite
```bash
# Если есть резервная копия
cp data/documents/documents_backup_*.db data/documents/documents.db
```

### 3. Обновите код
```bash
# Верните старые импорты в storage/__init__.py
# Верните SQLite в analytics/__init__.py
```

## 📋 Чек-лист миграции

- [ ] Остановлены старые контейнеры
- [ ] Запущен PostgreSQL контейнер
- [ ] База данных инициализирована
- [ ] Данные мигрированы (если есть)
- [ ] Все сервисы запущены
- [ ] Тесты пройдены
- [ ] Отчёты работают
- [ ] Бэкап создан

## ⚠️ Важные замечания

1. **Резервные копии** — всегда создавайте бэкапы перед миграцией
2. **Тестирование** — проверяйте функциональность после миграции
3. **Мониторинг** — следите за производительностью базы данных
4. **Обновления** — регулярно обновляйте PostgreSQL до последней версии

## 🆘 Устранение неполадок

### Проблемы подключения
```bash
# Проверка статуса контейнера
docker-compose ps postgres

# Просмотр логов
docker-compose logs postgres

# Проверка сети
docker network ls
docker network inspect assistant3_doc_network
```

### Проблемы производительности
```bash
# Анализ медленных запросов
docker exec -it doc_checker_postgres psql -U doc_user -d doc_checker -c "
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
"
```

### Проблемы с данными
```bash
# Проверка целостности
docker exec -it doc_checker_postgres psql -U doc_user -d doc_checker -c "
SELECT schemaname, tablename, attname, n_distinct
FROM pg_stats 
WHERE schemaname = 'public';
"
``` 