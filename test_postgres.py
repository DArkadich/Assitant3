#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы с PostgreSQL
"""

import os
import tempfile
import json
from datetime import datetime
from storage.postgres_storage import postgres_storage
from analytics import Analytics

def create_test_document(content, filename):
    """Создаёт тестовый файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    return filename

def test_postgres_connection():
    """Тестирует подключение к PostgreSQL"""
    print("🔌 Тестирование подключения к PostgreSQL...")
    
    try:
        stats = postgres_storage.get_database_stats()
        print(f"✅ Подключение успешно!")
        print(f"   Документов в базе: {stats['total_documents']}")
        print(f"   Контрагентов: {stats['total_counterparties']}")
        print(f"   Бизнес-цепочек: {stats['total_chains']}")
        print(f"   Незакрытых цепочек: {stats['unclosed_chains']}")
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False

def test_storage():
    """Тестирует систему хранения"""
    print("\n🧪 Тестирование системы хранения...")
    
    # Создаём тестовые документы
    test_docs = [
        {
            'content': 'ДОГОВОР №Д-2024-002\nООО "Тестовый Поставщик"\nИНН: 9876543210\nСумма: 2000000\nПредмет: Поставка оборудования',
            'filename': 'test_contract_pg.txt',
            'expected_type': 'договор'
        },
        {
            'content': 'СЧЕТ №456\nООО "Тестовый Поставщик"\nИНН: 9876543210\nСумма: 1000000\nДоговор: Д-2024-002',
            'filename': 'test_invoice_pg.txt',
            'expected_type': 'счет'
        },
        {
            'content': 'АКТ №789\nООО "Тестовый Поставщик"\nИНН: 9876543210\nСумма: 1000000\nДоговор: Д-2024-002',
            'filename': 'test_act_pg.txt',
            'expected_type': 'акт'
        }
    ]
    
    for i, doc in enumerate(test_docs):
        # Создаём тестовый файл
        test_file = create_test_document(doc['content'], doc['filename'])
        
        # Тестовые данные для сохранения
        test_data = {
            'doc_type': doc['expected_type'],
            'counterparty': 'ООО "Тестовый Поставщик"',
            'inn': '9876543210',
            'doc_number': f'{"Д-2024-002" if doc["expected_type"] == "договор" else "456" if doc["expected_type"] == "счет" else "789"}',
            'date': '2024-12-02',
            'amount': 2000000 if doc['expected_type'] == 'договор' else 1000000,
            'subject': 'Поставка оборудования',
            'contract_number': 'Д-2024-002'
        }
        
        try:
            # Сохраняем документ
            doc_id = postgres_storage.save_document(test_file, test_data, 54321)
            print(f"✅ Документ {doc['expected_type']} сохранён с ID: {doc_id}")
            
            # Удаляем тестовый файл
            os.remove(test_file)
        except Exception as e:
            print(f"❌ Ошибка сохранения {doc['expected_type']}: {e}")

def test_analytics():
    """Тестирует систему аналитики"""
    print("\n📊 Тестирование системы аналитики...")
    
    try:
        # Создаём экземпляр аналитики
        analytics = Analytics()
        
        # Тест отчёта по контрагентам
        report = analytics.generate_counterparty_report()
        print(f"✅ Отчёт по контрагентам: {report['summary']['total_counterparties']} контрагентов")
        
        # Тест отчёта по незакрытым цепочкам
        unclosed_report = analytics.generate_unclosed_chains_report()
        print(f"✅ Отчёт по незакрытым цепочкам: {unclosed_report['summary']['total_unclosed_chains']} цепочек")
        
        # Тест месячного отчёта
        monthly_report = analytics.generate_monthly_report(2024, 12)
        print(f"✅ Месячный отчёт за {monthly_report['period']}: {monthly_report['summary']['total_documents']} документов")
        
    except Exception as e:
        print(f"❌ Ошибка аналитики: {e}")

def test_chain_details():
    """Тестирует получение деталей цепочки"""
    print("\n🔗 Тестирование деталей цепочки...")
    
    try:
        chain_details = postgres_storage.get_chain_details('Д-2024-002')
        if chain_details:
            print(f"✅ Цепочка найдена: {chain_details['counterparty']}")
            print(f"   Документов в цепочке: {len(chain_details['documents'])}")
            print(f"   Общая сумма: {chain_details['total_amount']:,.2f} ₽")
            print(f"   Закрыто: {chain_details['closed_amount']:,.2f} ₽")
        else:
            print("⚠️ Цепочка не найдена")
    except Exception as e:
        print(f"❌ Ошибка получения деталей цепочки: {e}")

def test_views():
    """Тестирует представления базы данных"""
    print("\n👁️ Тестирование представлений базы данных...")
    
    try:
        # Тест представления незакрытых цепочек
        unclosed_chains = postgres_storage.get_unclosed_chains()
        print(f"✅ Представление незакрытых цепочек: {len(unclosed_chains)} записей")
        
        # Тест представления отчётов по контрагентам
        counterparty_reports = postgres_storage.get_counterparty_report()
        print(f"✅ Представление отчётов по контрагентам: {len(counterparty_reports)} записей")
        
    except Exception as e:
        print(f"❌ Ошибка представлений: {e}")

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов PostgreSQL системы\n")
    
    # Тестируем подключение
    if not test_postgres_connection():
        print("❌ Не удалось подключиться к PostgreSQL. Проверьте настройки.")
        return
    
    # Тестируем хранилище
    test_storage()
    
    # Тестируем аналитику
    test_analytics()
    
    # Тестируем детали цепочки
    test_chain_details()
    
    # Тестируем представления
    test_views()
    
    print("\n✨ Тестирование PostgreSQL завершено!")

if __name__ == "__main__":
    main() 