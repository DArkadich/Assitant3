import re
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Обязательные поля для разных типов документов
REQUIRED_FIELDS = {
    "акт": ["counterparty", "date", "amount"],
    "договор": ["counterparty", "date", "doc_number"],
    "счёт": ["counterparty", "date", "amount", "doc_number"],
    "упд": ["counterparty", "date", "amount", "doc_number", "inn"],
    "накладная": ["counterparty", "date", "amount", "doc_number"],
    # По умолчанию — все поля обязательны
    "default": ["counterparty", "date", "amount", "doc_number", "inn", "contract_number"]
}

class DocumentValidator:
    """Валидатор для проверки корректности извлеченных данных"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_document_data(self, doc_data: Dict, doc_type: Optional[str] = None) -> Tuple[bool, List[str], List[str]]:
        """
        Валидирует данные документа
        
        Returns:
            Tuple[bool, List[str], List[str]]: (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        # Определяем обязательные поля по типу документа
        doc_type_key = (doc_type or doc_data.get("doc_type") or "default").lower()
        required = REQUIRED_FIELDS.get(doc_type_key, REQUIRED_FIELDS["default"])
        for field in required:
            if not doc_data.get(field) or doc_data[field] == "-":
                self.errors.append(f"Отсутствует обязательное поле: {field}")

        # Валидируем только те поля, которые обязательны для этого типа документа
        if "inn" in required:
            self._validate_inn(doc_data.get('inn'))
        if "doc_number" in required:
            self._validate_doc_number(doc_data.get('doc_number'))
        if "date" in required:
            self._validate_date(doc_data.get('date'))
        if "amount" in required:
            self._validate_amount(doc_data.get('amount'))
        if "contract_number" in required:
            self._validate_contract_number(doc_data.get('contract_number'))
        self._validate_counterparty(doc_data.get('counterparty'))
        return (len(self.errors) == 0, self.errors, self.warnings)
    
    def _validate_required_fields(self, doc_data: Dict):
        """Проверяет наличие обязательных полей"""
        required_fields = ['doc_type', 'counterparty']
        
        for field in required_fields:
            if not doc_data.get(field) or doc_data.get(field) in ['не указано', 'не указан', 'Не указано', 'Не указан']:
                self.errors.append(f"Обязательное поле '{field}' не заполнено или содержит некорректное значение")
    
    def _validate_document_type(self, doc_type: str):
        """Валидирует тип документа"""
        if not doc_type:
            return
        
        valid_types = [
            'договор', 'счет', 'акт', 'накладная', 'счет-фактура', 
            'упд', 'выписка', 'иные'
        ]
        
        if doc_type.lower() not in [t.lower() for t in valid_types]:
            self.warnings.append(f"Неизвестный тип документа: {doc_type}")
    
    def _validate_counterparty(self, counterparty: str):
        """Валидирует название контрагента"""
        if not counterparty:
            return
        
        # Проверяем на минимальную длину
        if len(counterparty.strip()) < 3:
            self.errors.append(f"Название контрагента слишком короткое: {counterparty}")
        
        # Проверяем на наличие организационно-правовой формы
        org_forms = ['ООО', 'ОАО', 'ЗАО', 'ИП', 'АО', 'ПАО', 'НКО', 'ГУП', 'МУП']
        has_org_form = any(form in counterparty.upper() for form in org_forms)
        
        if not has_org_form:
            self.warnings.append(f"Возможно, отсутствует организационно-правовая форма: {counterparty}")
    
    def _validate_inn(self, inn: str):
        """Валидирует ИНН"""
        if not inn or inn in ['не указано', 'не указан', 'Не указано', 'Не указан']:
            self.warnings.append("ИНН не указан")
            return
        
        # Убираем лишние символы
        inn_clean = re.sub(r'[^\d]', '', inn)
        
        # Проверяем длину ИНН (10 для юр. лиц, 12 для ИП)
        if len(inn_clean) not in [10, 12]:
            self.errors.append(f"Некорректная длина ИНН: {inn} (должно быть 10 или 12 цифр)")
            return
        
        # Проверяем контрольные цифры (упрощенная проверка)
        if not self._check_inn_checksum(inn_clean):
            self.warnings.append(f"Возможно, некорректный ИНН: {inn}")
    
    def _check_inn_checksum(self, inn: str) -> bool:
        """Проверяет контрольные цифры ИНН"""
        if len(inn) == 10:
            weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        else:  # 12 цифр
            weights = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8, 0]
        
        checksum = sum(int(inn[i]) * weights[i] for i in range(len(weights))) % 11 % 10
        
        if len(inn) == 10:
            return checksum == int(inn[9])
        else:
            checksum2 = sum(int(inn[i]) * [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8][i] for i in range(11)) % 11 % 10
            return checksum == int(inn[10]) and checksum2 == int(inn[11])
    
    def _validate_doc_number(self, doc_number: str):
        """Валидирует номер документа"""
        if not doc_number:
            self.warnings.append("Номер документа не указан")
            return
        
        # Проверяем на минимальную длину
        if len(doc_number.strip()) < 2:
            self.errors.append(f"Номер документа слишком короткий: {doc_number}")
    
    def _validate_date(self, date: str):
        """Валидирует дату"""
        if not date:
            self.warnings.append("Дата не указана")
            return

        from datetime import datetime
        parsed = None
        # Попробуем распарсить дату в разных форматах
        for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d %B %Y г.", "%d %b %Y г."):
            try:
                parsed = datetime.strptime(date.strip(), fmt)
                break
            except Exception:
                continue
        if not parsed:
            # Попробуем парсинг русских месяцев
            try:
                import locale
                locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
                parsed = datetime.strptime(date.strip(), "%d %B %Y")
            except Exception:
                self.warnings.append(f"Не удалось распознать дату: {date}")
                return

        today = datetime.now().date()
        if parsed.date() > today:
            self.warnings.append(f"Дата в будущем: {date}")
    
    def _validate_amount(self, amount: str):
        """Валидирует сумму"""
        if not amount:
            self.warnings.append("Сумма не указана")
            return
        
        # Проверяем, что сумма положительная
        try:
            # Убираем валюту и парсим
            amount_clean = re.sub(r'[^\d\s,\.]', '', amount).strip().rstrip('.')
            if '.' in amount_clean and ',' in amount_clean:
                amount_clean = amount_clean.replace(',', '')
            elif ',' in amount_clean and '.' not in amount_clean:
                amount_clean = amount_clean.replace(' ', '').replace(',', '.')
            else:
                amount_clean = amount_clean.replace(' ', '')
            
            amount_value = float(amount_clean)
            if amount_value <= 0:
                self.errors.append(f"Сумма должна быть положительной: {amount}")
        except:
            self.errors.append(f"Некорректный формат суммы: {amount}")
    
    def _validate_contract_number(self, contract_number: str):
        """Валидирует номер договора"""
        if not contract_number:
            return
        
        # Проверяем на минимальную длину
        if len(contract_number.strip()) < 2:
            self.warnings.append(f"Номер договора слишком короткий: {contract_number}")
        
        # Проверяем на наличие ключевых слов
        contract_keywords = ['договор', 'контракт', 'соглашение', '№', 'N', 'number']
        has_keyword = any(keyword in contract_number.lower() for keyword in contract_keywords)
        
        if not has_keyword:
            self.warnings.append(f"Возможно, некорректный номер договора: {contract_number}")

# Глобальный экземпляр валидатора
validator = DocumentValidator() 