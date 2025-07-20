#!/usr/bin/env python3
"""
Тестовый скрипт для проверки системы хранения и аналитики
"""

import os
import tempfile
import json
from datetime import datetime
from storage import storage
from analytics import analytics

def create_test_document(content, filename):
    """Создаёт тестовый файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    return filename

def test_storage():
    """Тестирует систему хранения"""
    print("🧪 Тестирование системы хранения...")
    
    # Создаём тестовые документы
    test_docs = [
        {
            'content': 'ДОГОВОР №Д-2024-001\nООО "Поставщик"\nИНН: 1234567890\nСумма: 1000000\nПредмет: Поставка товаров',
            'filename': 'test_contract.txt',
            'expected_type': 'договор'
        },
        {
            'content': 'СЧЕТ №123\nООО "Поставщик"\nИНН: 1234567890\nСумма: 500000\nДоговор: Д-2024-001',
            'filename': 'test_invoice.txt',
            'expected_type': 'счет'
        },
        {
            'content': 'АКТ №456\nООО "Поставщик"\nИНН: 1234567890\nСумма: 500000\nДоговор: Д-2024-001',
            'filename': 'test_act.txt',
            'expected_type': 'акт'
        }
    ]
    
    for i, doc in enumerate(test_docs):
        # Создаём тестовый файл
        test_file = create_test_document(doc['content'], doc['filename'])
        
        # Тестовые данные для сохранения
        test_data = {
            'doc_type': doc['expected_type'],
            'counterparty': 'ООО "Поставщик"',
            'inn': '1234567890',
            'doc_number': f'{"Д-2024-001" if doc["expected_type"] == "договор" else "123" if doc["expected_type"] == "счет" else "456"}',
            'date': '2024-12-01',
            'amount': 1000000 if doc['expected_type'] == 'договор' else 500000,
            'subject': 'Поставка товаров',
            'contract_number': 'Д-2024-001'
        }
        
        try:
            # Сохраняем документ
            doc_id = storage.save_document(test_file, test_data, 12345)
            print(f"✅ Документ {doc['expected_type']} сохранён с ID: {doc_id}")
            
            # Удаляем тестовый файл
            os.remove(test_file)
        except Exception as e:
            print(f"❌ Ошибка сохранения {doc['expected_type']}: {e}")

def test_analytics():
    """Тестирует систему аналитики"""
    print("\n📊 Тестирование системы аналитики...")
    
    try:
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
        chain_details = storage.get_chain_details('Д-2024-001')
        if chain_details:
            print(f"✅ Цепочка найдена: {chain_details['counterparty']}")
            print(f"   Документов в цепочке: {len(chain_details['documents'])}")
            print(f"   Общая сумма: {chain_details['total_amount']:,.2f} ₽")
            print(f"   Закрыто: {chain_details['closed_amount']:,.2f} ₽")
        else:
            print("⚠️ Цепочка не найдена")
    except Exception as e:
        print(f"❌ Ошибка получения деталей цепочки: {e}")

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов системы хранения и аналитики\n")
    
    # Тестируем хранилище
    test_storage()
    
    # Тестируем аналитику
    test_analytics()
    
    # Тестируем детали цепочки
    test_chain_details()
    
    print("\n✨ Тестирование завершено!")

if __name__ == "__main__":
    main() 