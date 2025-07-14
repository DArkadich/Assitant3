import os
import shutil
from datetime import datetime
from typing import Dict, Optional

def create_folder_structure(base_path: str, year: str = None) -> Dict[str, str]:
    """Создаёт структуру папок для документов"""
    if not year:
        year = datetime.now().strftime("%Y")
    
    folders = {
        'счет': os.path.join(base_path, year, 'Счета'),
        'акт': os.path.join(base_path, year, 'Акты'),
        'договор': os.path.join(base_path, year, 'Договора'),
        'накладная': os.path.join(base_path, year, 'Накладные'),
        'квитанция': os.path.join(base_path, year, 'Квитанции'),
        'платежное поручение': os.path.join(base_path, year, 'Платёжные поручения'),
        'прочее': os.path.join(base_path, year, 'Прочее'),
    }
    
    # Создаём папки
    for folder in folders.values():
        os.makedirs(folder, exist_ok=True)
    
    return folders

def get_target_folder(doc_type: str, company: str, base_path: str, year: str = None, direction: str = None) -> str:
    """Определяет целевую папку для документа"""
    folders = create_folder_structure(base_path, year)
    doc_type_key = doc_type.lower().replace('ё', 'е') if doc_type else ''
    folder_type = folders.get(doc_type_key, folders['прочее'])

    # Для платёжных поручений добавляем подпапку direction
    if doc_type_key == 'платежное поручение' and direction:
        folder_type = os.path.join(folder_type, direction)

    if company:
        safe_company = "".join(c for c in company if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_company = safe_company.replace(' ', '_')
        target_folder = os.path.join(folder_type, safe_company)
    else:
        target_folder = folder_type

    os.makedirs(target_folder, exist_ok=True)
    return target_folder

def generate_filename(original_name: str, doc_type: str, doc_number: str, 
                     amount: Optional[float] = None, date: str = "") -> str:
    """Генерирует имя файла по шаблону"""
    # Извлекаем расширение
    name, ext = os.path.splitext(original_name)
    
    # Формируем части имени
    parts = []
    
    if doc_type and doc_type != "неизвестно":
        parts.append(doc_type.capitalize())
    
    if doc_number:
        parts.append(f"№{doc_number}")
    
    if amount:
        parts.append(f"на_{int(amount)}")
    
    if date:
        # Парсим дату и форматируем
        try:
            # Пробуем разные форматы даты
            for fmt in ['%d.%m.%Y', '%Y.%m.%d', '%d/%m/%Y']:
                try:
                    parsed_date = datetime.strptime(date, fmt)
                    parts.append(parsed_date.strftime('%Y-%m-%d'))
                    break
                except ValueError:
                    continue
        except:
            parts.append(date)
    
    # Если ничего не нашли, используем оригинальное имя
    if not parts:
        parts.append(name)
    
    # Собираем имя файла
    new_name = "_".join(parts) + ext
    
    return new_name

def move_document_to_folder(source_path: str, target_folder: str, 
                          new_filename: str) -> str:
    """Перемещает документ в целевую папку"""
    target_path = os.path.join(target_folder, new_filename)
    
    # Если файл с таким именем уже существует, добавляем номер
    counter = 1
    original_target = target_path
    while os.path.exists(target_path):
        name, ext = os.path.splitext(original_target)
        target_path = f"{name}_{counter}{ext}"
        counter += 1
    
    # Перемещаем файл
    shutil.move(source_path, target_path)
    
    return target_path 