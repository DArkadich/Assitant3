import os
import shutil
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager
import re

class PostgresStorage:
    def __init__(self, base_path: str = "data/documents", db_url: str = None):
        self.base_path = Path(base_path)
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://doc_user:doc_password@localhost:5432/doc_checker")
        self._init_storage()
        self._init_database()
    
    def _init_storage(self):
        """Создаёт структуру папок для хранения документов"""
        # Основные папки по типам документов
        doc_types = ["договоры", "счета", "акты", "накладные", "счет-фактуры", "упд", "выписки", "иные"]
        for doc_type in doc_types:
            (self.base_path / doc_type).mkdir(parents=True, exist_ok=True)
        
        # Папка для временных файлов
        (self.base_path / "temp").mkdir(parents=True, exist_ok=True)
        
        logging.info(f"Инициализирована структура хранения в {self.base_path}")
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к базе данных"""
        conn = None
        try:
            conn = psycopg2.connect(self.db_url)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Ошибка подключения к базе данных: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _init_database(self):
        """Проверяет подключение к базе данных"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()
                    logging.info(f"Подключение к PostgreSQL: {version[0]}")
        except Exception as e:
            logging.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    def _parse_russian_date(self, date_str: str) -> str:
        """
        Парсит русскую дату в формат YYYY-MM-DD для PostgreSQL
        
        Примеры:
        - "23 июня 2025 г." -> "2025-06-23"
        - "15 января 2024 года" -> "2024-01-15"
        - "2024-12-31" -> "2024-12-31" (уже в правильном формате)
        """
        if not date_str:
            return None
        
        # Если дата уже в формате YYYY-MM-DD, возвращаем как есть
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        
        # Словарь месяцев
        months = {
            'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
            'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
            'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
        }
        
        # Паттерны для парсинга русских дат
        patterns = [
            r'(\d{1,2})\s+(\w+)\s+(\d{4})\s*г?\.?',  # "23 июня 2025 г."
            r'(\d{1,2})\s+(\w+)\s+(\d{4})\s+года',   # "15 января 2024 года"
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',        # "23.06.2025"
            r'(\d{1,2})/(\d{1,2})/(\d{4})',          # "23/06/2025"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                if len(match.groups()) == 3:
                    day, month, year = match.groups()
                    
                    # Если месяц - число
                    if month.isdigit():
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    
                    # Если месяц - русское название
                    month_lower = month.lower()
                    if month_lower in months:
                        return f"{year}-{months[month_lower]}-{day.zfill(2)}"
        
        # Если не удалось распарсить, возвращаем None
        logging.warning(f"Не удалось распарсить дату: {date_str}")
        return None
    
    def _parse_russian_amount(self, amount_str: str) -> float:
        """
        Парсит русскую сумму в числовое значение для PostgreSQL
        
        Примеры:
        - "1 570 134,00 руб." -> 1570134.00
        - "1,234.56 руб." -> 1234.56
        - "1234.56" -> 1234.56
        - "1 234 567" -> 1234567.0
        """
        if not amount_str:
            return 0.0
        
        # Если уже число в правильном формате, возвращаем как есть
        try:
            return float(amount_str)
        except ValueError:
            pass
        
        # Убираем валюту и лишние символы, оставляем только цифры, пробелы, запятые и точки
        amount_clean = re.sub(r'[^\d\s,\.]', '', amount_str).strip()
        # Убираем точки в конце (часто это артефакты от "руб.")
        amount_clean = amount_clean.rstrip('.')
        
        # Если пустая строка после очистки
        if not amount_clean:
            return 0.0
        
        try:
            # Определяем формат по наличию точек и запятых
            if '.' in amount_clean and ',' in amount_clean:
                # Формат "1,234.56" - запятая как разделитель тысяч, точка как десятичный
                amount_clean = amount_clean.replace(',', '')
            elif ',' in amount_clean and '.' not in amount_clean:
                # Формат "1 570 134,00" - запятая как десятичный разделитель
                amount_clean = amount_clean.replace(' ', '').replace(',', '.')
            else:
                # Простой формат, убираем пробелы
                amount_clean = amount_clean.replace(' ', '')
            
            # Парсим как float
            return float(amount_clean)
        except ValueError:
            logging.warning(f"Не удалось распарсить сумму: {amount_str}")
            return 0.0
    
    def save_document(self, file_path: str, doc_data: Dict, telegram_user_id: int) -> int:
        """
        Сохраняет документ в соответствующую папку и записывает в БД
        
        Returns:
            int: ID документа в базе данных
        """
        # Определяем папку для сохранения
        doc_type = doc_data.get('doc_type', 'иные')
        counterparty = doc_data.get('counterparty', 'неизвестно')
        
        # Создаём безопасное имя папки контрагента
        safe_counterparty = self._sanitize_filename(counterparty)
        
        # Путь для сохранения: data/documents/{doc_type}/{counterparty}/
        target_dir = self.base_path / doc_type / safe_counterparty
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Копируем файл
        original_filename = os.path.basename(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"{timestamp}_{original_filename}"
        target_path = target_dir / new_filename
        
        shutil.copy2(file_path, target_path)
        
        # Сохраняем в базу данных
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Парсим дату и сумму в правильный формат
                parsed_date = self._parse_russian_date(doc_data.get('date'))
                parsed_amount = self._parse_russian_amount(doc_data.get('amount'))
                
                # Вставляем документ
                cursor.execute('''
                    INSERT INTO documents (
                        filename, original_filename, doc_type, counterparty, inn, 
                        doc_number, date, amount, subject, contract_number, 
                        storage_path, telegram_user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (
                    new_filename, original_filename, doc_type, counterparty,
                    doc_data.get('inn'), doc_data.get('doc_number'), parsed_date,
                    parsed_amount, doc_data.get('subject'), doc_data.get('contract_number'),
                    str(target_path), telegram_user_id
                ))
                
                doc_id = cursor.fetchone()[0]
                
                # Обновляем статистику контрагента
                self._update_counterparty_stats(cursor, counterparty, doc_data.get('inn'), 
                                               parsed_amount, parsed_date)
                
                # Если это договор, создаём новую бизнес-цепочку
                if doc_type == 'договор':
                    self._create_business_chain(cursor, doc_id, doc_data, parsed_date, parsed_amount)
                
                # Если это счёт или закрывающий документ, связываем с существующей цепочкой
                elif doc_type in ['счет', 'акт', 'накладная', 'счет-фактура', 'упд']:
                    self._link_to_business_chain(cursor, doc_id, doc_data, parsed_date, parsed_amount)
                
                conn.commit()
        
        logging.info(f"Документ сохранён: {target_path} (ID: {doc_id})")
        return doc_id
    
    def _sanitize_filename(self, filename: str) -> str:
        """Создаёт безопасное имя файла/папки"""
        import re
        # Заменяем недопустимые символы на подчёркивание
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Ограничиваем длину
        return safe_name[:100]
    
    def _update_counterparty_stats(self, cursor, counterparty: str, inn: str, 
                                  amount: float, date: str):
        """Обновляет статистику по контрагенту"""
        # Проверяем, есть ли уже контрагент
        cursor.execute('SELECT id, total_amount, document_count FROM counterparties WHERE inn = %s OR name = %s', 
                      (inn, counterparty))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующего
            doc_count = existing[2] + 1
            total_amount = existing[1] + (amount or 0)
            cursor.execute('''
                UPDATE counterparties 
                SET total_amount = %s, document_count = %s, last_document_date = %s
                WHERE id = %s
            ''', (total_amount, doc_count, date, existing[0]))
        else:
            # Создаём нового
            cursor.execute('''
                INSERT INTO counterparties (name, inn, first_document_date, last_document_date, 
                                          total_amount, document_count)
                VALUES (%s, %s, %s, %s, %s, 1)
            ''', (counterparty, inn, date, date, amount or 0))
    
    def _create_business_chain(self, cursor, doc_id: int, doc_data: Dict, parsed_date: str, parsed_amount: float):
        """Создаёт новую бизнес-цепочку для договора"""
        contract_number = doc_data.get('contract_number')
        counterparty = doc_data.get('counterparty')
        
        if contract_number and counterparty:
            cursor.execute('''
                INSERT INTO business_chains (contract_number, contract_doc_id, counterparty, total_amount)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', (contract_number, doc_id, counterparty, parsed_amount))
            
            chain_id = cursor.fetchone()[0]
            
            # Связываем договор с цепочкой
            cursor.execute('''
                INSERT INTO chain_links (chain_id, document_id, link_type, amount, date)
                VALUES (%s, %s, %s, %s, %s)
            ''', (chain_id, doc_id, 'contract', parsed_amount, parsed_date))
    
    def _link_to_business_chain(self, cursor, doc_id: int, doc_data: Dict, parsed_date: str, parsed_amount: float):
        """Связывает документ с существующей бизнес-цепочкой"""
        contract_number = doc_data.get('contract_number')
        if not contract_number:
            return
        
        # Ищем цепочку по номеру договора
        cursor.execute('SELECT id FROM business_chains WHERE contract_number = %s', (contract_number,))
        chain = cursor.fetchone()
        
        if chain:
            chain_id = chain[0]
            doc_type = doc_data.get('doc_type')
            
            # Определяем тип связи
            link_type = 'invoice' if doc_type == 'счет' else 'closing'
            
            # Связываем документ с цепочкой
            cursor.execute('''
                INSERT INTO chain_links (chain_id, document_id, link_type, amount, date)
                VALUES (%s, %s, %s, %s, %s)
            ''', (chain_id, doc_id, link_type, parsed_amount, parsed_date))
            
            # Обновляем статистику цепочки
            if link_type == 'invoice':
                cursor.execute('''
                    UPDATE business_chains 
                    SET total_amount = total_amount + %s
                    WHERE id = %s
                ''', (amount, chain_id))
            elif link_type == 'closing':
                cursor.execute('''
                    UPDATE business_chains 
                    SET closed_amount = closed_amount + %s
                    WHERE id = %s
                ''', (amount, chain_id))
    
    def get_counterparty_report(self, counterparty: str = None) -> List[Dict]:
        """Получает отчёт по контрагентам"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if counterparty:
                    cursor.execute('''
                        SELECT * FROM counterparty_reports_view 
                        WHERE name ILIKE %s OR inn = %s
                    ''', (f'%{counterparty}%', counterparty))
                else:
                    cursor.execute('SELECT * FROM counterparty_reports_view')
                
                return [dict(row) for row in cursor.fetchall()]
    
    def get_unclosed_chains(self) -> List[Dict]:
        """Получает незакрытые бизнес-цепочки"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM unclosed_chains_view')
                return [dict(row) for row in cursor.fetchall()]
    
    def get_chain_details(self, contract_number: str) -> Dict:
        """Получает детали бизнес-цепочки"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Получаем основную информацию о цепочке
                cursor.execute('''
                    SELECT id, counterparty, total_amount, closed_amount, status, created_at
                    FROM business_chains 
                    WHERE contract_number = %s
                ''', (contract_number,))
                
                chain = cursor.fetchone()
                if not chain:
                    return None
                
                chain_dict = dict(chain)
                chain_id = chain_dict['id']
                
                # Получаем все документы в цепочке
                cursor.execute('''
                    SELECT d.doc_type, d.doc_number, d.date, d.amount, d.subject, cl.link_type
                    FROM chain_links cl
                    JOIN documents d ON cl.document_id = d.id
                    WHERE cl.chain_id = %s
                    ORDER BY d.date
                ''', (chain_id,))
                
                documents = [dict(row) for row in cursor.fetchall()]
                
                chain_dict['documents'] = documents
                chain_dict['remaining_amount'] = chain_dict['total_amount'] - chain_dict['closed_amount']
                
                return chain_dict
    
    def get_database_stats(self) -> Dict:
        """Получает статистику базы данных"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                stats = {}
                
                # Общая статистика
                cursor.execute('SELECT COUNT(*) as total_documents FROM documents')
                stats['total_documents'] = cursor.fetchone()['total_documents']
                
                cursor.execute('SELECT COUNT(*) as total_counterparties FROM counterparties')
                stats['total_counterparties'] = cursor.fetchone()['total_counterparties']
                
                cursor.execute('SELECT COUNT(*) as total_chains FROM business_chains')
                stats['total_chains'] = cursor.fetchone()['total_chains']
                
                cursor.execute('SELECT COUNT(*) as unclosed_chains FROM business_chains WHERE total_amount > closed_amount')
                stats['unclosed_chains'] = cursor.fetchone()['unclosed_chains']
                
                # Суммы
                cursor.execute('SELECT COALESCE(SUM(amount), 0) as total_amount FROM documents')
                stats['total_amount'] = cursor.fetchone()['total_amount']
                
                cursor.execute('''
                    SELECT COALESCE(SUM(total_amount - closed_amount), 0) as unclosed_amount 
                    FROM business_chains 
                    WHERE total_amount > closed_amount
                ''')
                stats['unclosed_amount'] = cursor.fetchone()['unclosed_amount']
                
                return stats

# Глобальный экземпляр хранилища PostgreSQL
postgres_storage = PostgresStorage() 