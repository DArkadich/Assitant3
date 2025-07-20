#!/usr/bin/env python3
"""
Скрипт для миграции данных из SQLite в PostgreSQL
"""

import sqlite3
import psycopg2
import logging
from datetime import datetime
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_data():
    """Мигрирует данные из SQLite в PostgreSQL"""
    
    # Пути к базам данных
    sqlite_path = "data/documents/documents.db"
    postgres_url = os.getenv("DATABASE_URL", "postgresql://doc_user:doc_password@localhost:5432/doc_checker")
    
    # Проверяем существование SQLite базы
    if not os.path.exists(sqlite_path):
        logger.error(f"SQLite база данных не найдена: {sqlite_path}")
        return False
    
    try:
        # Подключаемся к SQLite
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_cursor = sqlite_conn.cursor()
        
        # Подключаемся к PostgreSQL
        postgres_conn = psycopg2.connect(postgres_url)
        postgres_cursor = postgres_conn.cursor()
        
        logger.info("Начинаем миграцию данных...")
        
        # Мигрируем документы
        logger.info("Мигрируем документы...")
        sqlite_cursor.execute("SELECT * FROM documents")
        documents = sqlite_cursor.fetchall()
        
        for doc in documents:
            postgres_cursor.execute('''
                INSERT INTO documents (
                    id, filename, original_filename, doc_type, counterparty, inn,
                    doc_number, date, amount, subject, contract_number, storage_path,
                    telegram_user_id, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', doc)
        
        logger.info(f"Мигрировано {len(documents)} документов")
        
        # Мигрируем контрагентов
        logger.info("Мигрируем контрагентов...")
        sqlite_cursor.execute("SELECT * FROM counterparties")
        counterparties = sqlite_cursor.fetchall()
        
        for cp in counterparties:
            postgres_cursor.execute('''
                INSERT INTO counterparties (
                    id, name, inn, first_document_date, last_document_date,
                    total_amount, document_count, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', cp)
        
        logger.info(f"Мигрировано {len(counterparties)} контрагентов")
        
        # Мигрируем бизнес-цепочки
        logger.info("Мигрируем бизнес-цепочки...")
        sqlite_cursor.execute("SELECT * FROM business_chains")
        chains = sqlite_cursor.fetchall()
        
        for chain in chains:
            postgres_cursor.execute('''
                INSERT INTO business_chains (
                    id, contract_number, contract_doc_id, counterparty, total_amount,
                    paid_amount, closed_amount, status, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', chain)
        
        logger.info(f"Мигрировано {len(chains)} бизнес-цепочек")
        
        # Мигрируем связи в цепочках
        logger.info("Мигрируем связи в цепочках...")
        sqlite_cursor.execute("SELECT * FROM chain_links")
        links = sqlite_cursor.fetchall()
        
        for link in links:
            postgres_cursor.execute('''
                INSERT INTO chain_links (
                    id, chain_id, document_id, link_type, amount, date, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', link)
        
        logger.info(f"Мигрировано {len(links)} связей")
        
        # Обновляем последовательности
        logger.info("Обновляем последовательности...")
        postgres_cursor.execute("SELECT setval('documents_id_seq', (SELECT MAX(id) FROM documents))")
        postgres_cursor.execute("SELECT setval('counterparties_id_seq', (SELECT MAX(id) FROM counterparties))")
        postgres_cursor.execute("SELECT setval('business_chains_id_seq', (SELECT MAX(id) FROM business_chains))")
        postgres_cursor.execute("SELECT setval('chain_links_id_seq', (SELECT MAX(id) FROM chain_links))")
        
        # Фиксируем изменения
        postgres_conn.commit()
        
        logger.info("Миграция завершена успешно!")
        
        # Закрываем соединения
        sqlite_conn.close()
        postgres_conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка миграции: {e}")
        if 'postgres_conn' in locals():
            postgres_conn.rollback()
            postgres_conn.close()
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
        return False

def backup_sqlite():
    """Создаёт резервную копию SQLite базы"""
    sqlite_path = "data/documents/documents.db"
    if os.path.exists(sqlite_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"data/documents/documents_backup_{timestamp}.db"
        import shutil
        shutil.copy2(sqlite_path, backup_path)
        logger.info(f"Создана резервная копия: {backup_path}")
        return backup_path
    return None

def main():
    """Основная функция"""
    print("🔄 Миграция данных из SQLite в PostgreSQL")
    print("=" * 50)
    
    # Создаём резервную копию
    backup_path = backup_sqlite()
    
    # Выполняем миграцию
    if migrate_data():
        print("✅ Миграция завершена успешно!")
        if backup_path:
            print(f"📁 Резервная копия SQLite: {backup_path}")
        print("💡 Теперь можно удалить старую SQLite базу данных")
    else:
        print("❌ Миграция не удалась")
        if backup_path:
            print(f"📁 Резервная копия сохранена: {backup_path}")

if __name__ == "__main__":
    main() 