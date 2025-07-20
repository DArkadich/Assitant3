import os
import shutil
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

class DocumentStorage:
    def __init__(self, base_path: str = "data/documents"):
        self.base_path = Path(base_path)
        self.db_path = self.base_path / "documents.db"
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
    
    def _init_database(self):
        """Создаёт базу данных для учёта документов"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица документов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                counterparty TEXT,
                inn TEXT,
                doc_number TEXT,
                date TEXT,
                amount REAL,
                subject TEXT,
                contract_number TEXT,
                storage_path TEXT NOT NULL,
                telegram_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица контрагентов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS counterparties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                inn TEXT UNIQUE,
                first_document_date TIMESTAMP,
                last_document_date TIMESTAMP,
                total_amount REAL DEFAULT 0,
                document_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица бизнес-цепочек (договор → счета → платежи → закрывающие документы)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS business_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_number TEXT NOT NULL,
                contract_doc_id INTEGER,
                counterparty TEXT NOT NULL,
                total_amount REAL DEFAULT 0,
                paid_amount REAL DEFAULT 0,
                closed_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'active', -- active, closed, overdue
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_doc_id) REFERENCES documents (id)
            )
        ''')
        
        # Таблица связей документов в цепочке
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chain_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                link_type TEXT NOT NULL, -- contract, invoice, payment, closing
                amount REAL,
                date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chain_id) REFERENCES business_chains (id),
                FOREIGN KEY (document_id) REFERENCES documents (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info(f"База данных инициализирована: {self.db_path}")
    
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO documents (
                filename, original_filename, doc_type, counterparty, inn, 
                doc_number, date, amount, subject, contract_number, 
                storage_path, telegram_user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_filename, original_filename, doc_type, counterparty,
            doc_data.get('inn'), doc_data.get('doc_number'), doc_data.get('date'),
            doc_data.get('amount'), doc_data.get('subject'), doc_data.get('contract_number'),
            str(target_path), telegram_user_id
        ))
        
        doc_id = cursor.lastrowid
        
        # Обновляем статистику контрагента
        self._update_counterparty_stats(cursor, counterparty, doc_data.get('inn'), 
                                       doc_data.get('amount'), doc_data.get('date'))
        
        # Если это договор, создаём новую бизнес-цепочку
        if doc_type == 'договор':
            self._create_business_chain(cursor, doc_id, doc_data)
        
        # Если это счёт или закрывающий документ, связываем с существующей цепочкой
        elif doc_type in ['счет', 'акт', 'накладная', 'счет-фактура', 'упд']:
            self._link_to_business_chain(cursor, doc_id, doc_data)
        
        conn.commit()
        conn.close()
        
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
        cursor.execute('SELECT id, total_amount, document_count FROM counterparties WHERE inn = ? OR name = ?', 
                      (inn, counterparty))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующего
            doc_count = existing[2] + 1
            total_amount = existing[1] + (amount or 0)
            cursor.execute('''
                UPDATE counterparties 
                SET total_amount = ?, document_count = ?, last_document_date = ?
                WHERE id = ?
            ''', (total_amount, doc_count, date, existing[0]))
        else:
            # Создаём нового
            cursor.execute('''
                INSERT INTO counterparties (name, inn, first_document_date, last_document_date, 
                                          total_amount, document_count)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (counterparty, inn, date, date, amount or 0))
    
    def _create_business_chain(self, cursor, doc_id: int, doc_data: Dict):
        """Создаёт новую бизнес-цепочку для договора"""
        contract_number = doc_data.get('contract_number')
        counterparty = doc_data.get('counterparty')
        amount = doc_data.get('amount', 0)
        
        if contract_number and counterparty:
            cursor.execute('''
                INSERT INTO business_chains (contract_number, contract_doc_id, counterparty, total_amount)
                VALUES (?, ?, ?, ?)
            ''', (contract_number, doc_id, counterparty, amount))
            
            chain_id = cursor.lastrowid
            
            # Связываем договор с цепочкой
            cursor.execute('''
                INSERT INTO chain_links (chain_id, document_id, link_type, amount, date)
                VALUES (?, ?, 'contract', ?, ?)
            ''', (chain_id, doc_id, amount, doc_data.get('date')))
    
    def _link_to_business_chain(self, cursor, doc_id: int, doc_data: Dict):
        """Связывает документ с существующей бизнес-цепочкой"""
        contract_number = doc_data.get('contract_number')
        if not contract_number:
            return
        
        # Ищем цепочку по номеру договора
        cursor.execute('SELECT id FROM business_chains WHERE contract_number = ?', (contract_number,))
        chain = cursor.fetchone()
        
        if chain:
            chain_id = chain[0]
            doc_type = doc_data.get('doc_type')
            amount = doc_data.get('amount', 0)
            
            # Определяем тип связи
            link_type = 'invoice' if doc_type == 'счет' else 'closing'
            
            # Связываем документ с цепочкой
            cursor.execute('''
                INSERT INTO chain_links (chain_id, document_id, link_type, amount, date)
                VALUES (?, ?, ?, ?, ?)
            ''', (chain_id, doc_id, link_type, amount, doc_data.get('date')))
            
            # Обновляем статистику цепочки
            if link_type == 'invoice':
                cursor.execute('''
                    UPDATE business_chains 
                    SET total_amount = total_amount + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (amount, chain_id))
            elif link_type == 'closing':
                cursor.execute('''
                    UPDATE business_chains 
                    SET closed_amount = closed_amount + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (amount, chain_id))
    
    def get_counterparty_report(self, counterparty: str = None) -> List[Dict]:
        """Получает отчёт по контрагентам"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if counterparty:
            cursor.execute('''
                SELECT name, inn, first_document_date, last_document_date, 
                       total_amount, document_count
                FROM counterparties 
                WHERE name LIKE ? OR inn = ?
            ''', (f'%{counterparty}%', counterparty))
        else:
            cursor.execute('''
                SELECT name, inn, first_document_date, last_document_date, 
                       total_amount, document_count
                FROM counterparties 
                ORDER BY total_amount DESC
            ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'name': row[0],
                'inn': row[1],
                'first_document_date': row[2],
                'last_document_date': row[3],
                'total_amount': row[4],
                'document_count': row[5]
            })
        
        conn.close()
        return results
    
    def get_unclosed_chains(self) -> List[Dict]:
        """Получает незакрытые бизнес-цепочки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT bc.contract_number, bc.counterparty, bc.total_amount, 
                   bc.closed_amount, bc.created_at,
                   (bc.total_amount - bc.closed_amount) as remaining_amount
            FROM business_chains bc
            WHERE bc.total_amount > bc.closed_amount
            ORDER BY remaining_amount DESC
        ''')
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'contract_number': row[0],
                'counterparty': row[1],
                'total_amount': row[2],
                'closed_amount': row[3],
                'created_at': row[4],
                'remaining_amount': row[5]
            })
        
        conn.close()
        return results
    
    def get_chain_details(self, contract_number: str) -> Dict:
        """Получает детали бизнес-цепочки"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Получаем основную информацию о цепочке
        cursor.execute('''
            SELECT id, counterparty, total_amount, closed_amount, status, created_at
            FROM business_chains 
            WHERE contract_number = ?
        ''', (contract_number,))
        
        chain = cursor.fetchone()
        if not chain:
            conn.close()
            return None
        
        chain_id, counterparty, total_amount, closed_amount, status, created_at = chain
        
        # Получаем все документы в цепочке
        cursor.execute('''
            SELECT d.doc_type, d.doc_number, d.date, d.amount, d.subject, cl.link_type
            FROM chain_links cl
            JOIN documents d ON cl.document_id = d.id
            WHERE cl.chain_id = ?
            ORDER BY d.date
        ''', (chain_id,))
        
        documents = []
        for row in cursor.fetchall():
            documents.append({
                'doc_type': row[0],
                'doc_number': row[1],
                'date': row[2],
                'amount': row[3],
                'subject': row[4],
                'link_type': row[5]
            })
        
        conn.close()
        
        return {
            'contract_number': contract_number,
            'counterparty': counterparty,
            'total_amount': total_amount,
            'closed_amount': closed_amount,
            'remaining_amount': total_amount - closed_amount,
            'status': status,
            'created_at': created_at,
            'documents': documents
        }

# Импортируем PostgreSQL хранилище
from .postgres_storage import postgres_storage

# Глобальный экземпляр хранилища (PostgreSQL)
storage = postgres_storage 