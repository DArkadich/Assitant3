import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import json
import os
from contextlib import contextmanager

class Analytics:
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://doc_user:doc_password@localhost:5432/doc_checker")
    
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
    
    def generate_counterparty_report(self, counterparty: str = None, 
                                   start_date: str = None, end_date: str = None) -> Dict:
        """
        Генерирует отчёт по контрагентам
        
        Args:
            counterparty: конкретный контрагент (если None - все)
            start_date: начальная дата в формате YYYY-MM-DD
            end_date: конечная дата в формате YYYY-MM-DD
        """
        with self.get_connection() as conn:
            # Базовый запрос
            query = '''
                SELECT 
                    c.name,
                    c.inn,
                    c.first_document_date,
                    c.last_document_date,
                    c.total_amount,
                    c.document_count,
                    COUNT(CASE WHEN d.doc_type = 'договор' THEN 1 END) as contracts_count,
                    COUNT(CASE WHEN d.doc_type = 'счет' THEN 1 END) as invoices_count,
                    COUNT(CASE WHEN d.doc_type IN ('акт', 'накладная', 'счет-фактура', 'упд') THEN 1 END) as closing_docs_count,
                    COALESCE(SUM(CASE WHEN d.doc_type = 'договор' THEN d.amount ELSE 0 END), 0) as contracts_amount,
                    COALESCE(SUM(CASE WHEN d.doc_type = 'счет' THEN d.amount ELSE 0 END), 0) as invoices_amount,
                    COALESCE(SUM(CASE WHEN d.doc_type IN ('акт', 'накладная', 'счет-фактура', 'упд') THEN d.amount ELSE 0 END), 0) as closing_amount
                FROM counterparties c
                LEFT JOIN documents d ON c.name = d.counterparty OR c.inn = d.inn
            '''
            
            conditions = []
            params = []
            
            if counterparty:
                conditions.append("(c.name ILIKE %s OR c.inn = %s)")
                params.extend([f'%{counterparty}%', counterparty])
            
            if start_date:
                conditions.append("d.date >= %s")
                params.append(start_date)
            
            if end_date:
                conditions.append("d.date <= %s")
                params.append(end_date)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " GROUP BY c.id, c.name, c.inn ORDER BY c.total_amount DESC"
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]
        
        # Формируем отчёт
        report = {
            'generated_at': datetime.now().isoformat(),
            'period': {'start': start_date, 'end': end_date},
            'counterparty_filter': counterparty,
            'summary': {
                'total_counterparties': len(results),
                'total_amount': sum(float(r['total_amount']) for r in results),
                'total_documents': sum(r['document_count'] for r in results)
            },
            'counterparties': []
        }
        
        for row in results:
            report['counterparties'].append({
                'name': row['name'],
                'inn': row['inn'],
                'first_document_date': row['first_document_date'].isoformat() if row['first_document_date'] else None,
                'last_document_date': row['last_document_date'].isoformat() if row['last_document_date'] else None,
                'total_amount': float(row['total_amount']),
                'document_count': row['document_count'],
                'contracts_count': row['contracts_count'],
                'invoices_count': row['invoices_count'],
                'closing_docs_count': row['closing_docs_count'],
                'contracts_amount': float(row['contracts_amount']),
                'invoices_amount': float(row['invoices_amount']),
                'closing_amount': float(row['closing_amount']),
                'unclosed_amount': float(row['invoices_amount']) - float(row['closing_amount'])
            })
        
        return report
    
    def generate_unclosed_chains_report(self) -> Dict:
        """Генерирует отчёт по незакрытым бизнес-цепочкам"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT * FROM unclosed_chains_view')
                results = [dict(row) for row in cursor.fetchall()]
        
        # Анализируем возраст незакрытых цепочек
        now = datetime.now()
        
        # Категоризируем по возрасту
        def categorize_age(days):
            if days <= 30:
                return 'новые'
            elif days <= 90:
                return 'средние'
            else:
                return 'старые'
        
        for row in results:
            row['age_category'] = categorize_age(row['age_days'])
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_unclosed_chains': len(results),
                'total_remaining_amount': sum(float(r['remaining_amount']) for r in results),
                'average_remaining_amount': sum(float(r['remaining_amount']) for r in results) / len(results) if results else 0,
                'oldest_chain_days': max(r['age_days'] for r in results) if results else 0,
                'newest_chain_days': min(r['age_days'] for r in results) if results else 0
            },
            'by_age_category': {
                'новые': {
                    'count': len([r for r in results if r['age_category'] == 'новые']),
                    'amount': sum(float(r['remaining_amount']) for r in results if r['age_category'] == 'новые')
                },
                'средние': {
                    'count': len([r for r in results if r['age_category'] == 'средние']),
                    'amount': sum(float(r['remaining_amount']) for r in results if r['age_category'] == 'средние')
                },
                'старые': {
                    'count': len([r for r in results if r['age_category'] == 'старые']),
                    'amount': sum(float(r['remaining_amount']) for r in results if r['age_category'] == 'старые')
                }
            },
            'chains': []
        }
        
        for row in results:
            report['chains'].append({
                'contract_number': row['contract_number'],
                'counterparty': row['counterparty'],
                'total_amount': float(row['total_amount']),
                'closed_amount': float(row['closed_amount']),
                'remaining_amount': float(row['remaining_amount']),
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'age_days': row['age_days'],
                'age_category': row['age_category'],
                'documents_count': row['documents_count'],
                'contracts_count': row['contracts_count'],
                'invoices_count': row['invoices_count'],
                'closing_count': row['closing_count']
            })
        
        return report
    
    def generate_monthly_report(self, year: int = None, month: int = None) -> Dict:
        """Генерирует месячный отчёт по документам"""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        with self.get_connection() as conn:
            # Получаем документы за месяц
            start_date = f"{year:04d}-{month:02d}-01"
            if month == 12:
                end_date = f"{year+1:04d}-01-01"
            else:
                end_date = f"{year:04d}-{month+1:02d}-01"
            
            query = '''
                SELECT 
                    doc_type,
                    counterparty,
                    amount,
                    date,
                    COUNT(*) as count
                FROM documents 
                WHERE date >= %s AND date < %s
                GROUP BY doc_type, counterparty
                ORDER BY doc_type, amount DESC
            '''
            
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, [start_date, end_date])
                results = [dict(row) for row in cursor.fetchall()]
        
        # Создаём DataFrame для анализа
        df = pd.DataFrame(results)
        
        if df.empty:
            return {
                'period': f"{year:04d}-{month:02d}",
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'total_documents': 0,
                    'total_amount': 0,
                    'unique_counterparties': 0,
                    'document_types': 0
                },
                'by_document_type': {},
                'top_counterparties': {}
            }
        
        # Группируем по типам документов
        doc_type_summary = df.groupby('doc_type').agg({
            'amount': ['sum', 'count'],
            'counterparty': 'nunique'
        }).round(2)
        
        doc_type_summary.columns = ['total_amount', 'document_count', 'counterparties_count']
        
        # Топ контрагентов по сумме
        top_counterparties = df.groupby('counterparty').agg({
            'amount': 'sum',
            'doc_type': 'count'
        }).sort_values('amount', ascending=False).head(10)
        
        report = {
            'period': f"{year:04d}-{month:02d}",
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_documents': df['count'].sum(),
                'total_amount': df['amount'].sum(),
                'unique_counterparties': df['counterparty'].nunique(),
                'document_types': len(df['doc_type'].unique())
            },
            'by_document_type': doc_type_summary.to_dict('index'),
            'top_counterparties': top_counterparties.to_dict('index')
        }
        
        return report
    
    def export_to_excel(self, report: Dict, filename: str):
        """Экспортирует отчёт в Excel"""
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Сводка
            summary_df = pd.DataFrame([report['summary']])
            summary_df.to_excel(writer, sheet_name='Сводка', index=False)
            
            # Контрагенты
            if 'counterparties' in report:
                counterparties_df = pd.DataFrame(report['counterparties'])
                counterparties_df.to_excel(writer, sheet_name='Контрагенты', index=False)
            
            # Цепочки
            if 'chains' in report:
                chains_df = pd.DataFrame(report['chains'])
                chains_df.to_excel(writer, sheet_name='Незакрытые цепочки', index=False)
            
            # По типам документов
            if 'by_document_type' in report:
                doc_types_df = pd.DataFrame(report['by_document_type']).T
                doc_types_df.to_excel(writer, sheet_name='По типам документов')
            
            # Топ контрагентов
            if 'top_counterparties' in report:
                top_df = pd.DataFrame(report['top_counterparties']).T
                top_df.to_excel(writer, sheet_name='Топ контрагентов')
    
    def export_to_csv(self, report: Dict, base_filename: str):
        """Экспортирует отчёт в CSV файлы"""
        if 'counterparties' in report:
            counterparties_df = pd.DataFrame(report['counterparties'])
            counterparties_df.to_csv(f"{base_filename}_counterparties.csv", index=False, encoding='utf-8-sig')
        
        if 'chains' in report:
            chains_df = pd.DataFrame(report['chains'])
            chains_df.to_csv(f"{base_filename}_chains.csv", index=False, encoding='utf-8-sig') 