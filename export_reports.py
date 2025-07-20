#!/usr/bin/env python3
"""
Скрипт для экспорта отчётов из базы данных документов
"""

import argparse
import os
from datetime import datetime
from analytics import analytics
from storage import storage

def main():
    parser = argparse.ArgumentParser(description='Экспорт отчётов из базы документов')
    parser.add_argument('--type', choices=['counterparties', 'unclosed', 'monthly'], 
                       required=True, help='Тип отчёта')
    parser.add_argument('--output', default='reports', help='Папка для сохранения отчётов')
    parser.add_argument('--format', choices=['excel', 'csv'], default='excel', 
                       help='Формат экспорта')
    parser.add_argument('--counterparty', help='Контрагент для фильтрации')
    parser.add_argument('--year', type=int, help='Год для месячного отчёта')
    parser.add_argument('--month', type=int, help='Месяц для месячного отчёта')
    
    args = parser.parse_args()
    
    # Создаём папку для отчётов
    os.makedirs(args.output, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if args.type == 'counterparties':
        print("Генерирую отчёт по контрагентам...")
        report = analytics.generate_counterparty_report(counterparty=args.counterparty)
        
        if args.format == 'excel':
            filename = os.path.join(args.output, f"counterparties_report_{timestamp}.xlsx")
            analytics.export_to_excel(report, filename)
            print(f"Отчёт сохранён: {filename}")
        else:
            base_filename = os.path.join(args.output, f"counterparties_report_{timestamp}")
            analytics.export_to_csv(report, base_filename)
            print(f"Отчёты сохранены: {base_filename}_*.csv")
    
    elif args.type == 'unclosed':
        print("Генерирую отчёт по незакрытым цепочкам...")
        report = analytics.generate_unclosed_chains_report()
        
        if args.format == 'excel':
            filename = os.path.join(args.output, f"unclosed_chains_{timestamp}.xlsx")
            analytics.export_to_excel(report, filename)
            print(f"Отчёт сохранён: {filename}")
        else:
            base_filename = os.path.join(args.output, f"unclosed_chains_{timestamp}")
            analytics.export_to_csv(report, base_filename)
            print(f"Отчёты сохранены: {base_filename}_*.csv")
    
    elif args.type == 'monthly':
        print("Генерирую месячный отчёт...")
        report = analytics.generate_monthly_report(args.year, args.month)
        
        if args.format == 'excel':
            filename = os.path.join(args.output, f"monthly_report_{report['period']}_{timestamp}.xlsx")
            analytics.export_to_excel(report, filename)
            print(f"Отчёт сохранён: {filename}")
        else:
            base_filename = os.path.join(args.output, f"monthly_report_{report['period']}_{timestamp}")
            analytics.export_to_csv(report, base_filename)
            print(f"Отчёты сохранены: {base_filename}_*.csv")
    
    print("Экспорт завершён!")

if __name__ == "__main__":
    main() 