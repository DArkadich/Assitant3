-- Инициализация базы данных для системы документов
-- Создаётся автоматически при первом запуске PostgreSQL контейнера

-- Создание таблицы документов
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    doc_type VARCHAR(50) NOT NULL,
    counterparty VARCHAR(255),
    inn VARCHAR(20),
    doc_number VARCHAR(100),
    date DATE,
    amount DECIMAL(15,2),
    subject TEXT,
    contract_number VARCHAR(100),
    storage_path TEXT NOT NULL,
    telegram_user_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы контрагентов
CREATE TABLE IF NOT EXISTS counterparties (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    inn VARCHAR(20) UNIQUE,
    first_document_date DATE,
    last_document_date DATE,
    total_amount DECIMAL(15,2) DEFAULT 0,
    document_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы бизнес-цепочек
CREATE TABLE IF NOT EXISTS business_chains (
    id SERIAL PRIMARY KEY,
    contract_number VARCHAR(100) NOT NULL,
    contract_doc_id INTEGER REFERENCES documents(id),
    counterparty VARCHAR(255) NOT NULL,
    total_amount DECIMAL(15,2) DEFAULT 0,
    paid_amount DECIMAL(15,2) DEFAULT 0,
    closed_amount DECIMAL(15,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active', -- active, closed, overdue
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблицы связей документов в цепочке
CREATE TABLE IF NOT EXISTS chain_links (
    id SERIAL PRIMARY KEY,
    chain_id INTEGER NOT NULL REFERENCES business_chains(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    link_type VARCHAR(20) NOT NULL, -- contract, invoice, payment, closing
    amount DECIMAL(15,2),
    date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов для улучшения производительности
CREATE INDEX IF NOT EXISTS idx_documents_counterparty ON documents(counterparty);
CREATE INDEX IF NOT EXISTS idx_documents_inn ON documents(inn);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_documents_date ON documents(date);
CREATE INDEX IF NOT EXISTS idx_documents_contract_number ON documents(contract_number);

CREATE INDEX IF NOT EXISTS idx_business_chains_contract_number ON business_chains(contract_number);
CREATE INDEX IF NOT EXISTS idx_business_chains_counterparty ON business_chains(counterparty);
CREATE INDEX IF NOT EXISTS idx_business_chains_status ON business_chains(status);

CREATE INDEX IF NOT EXISTS idx_chain_links_chain_id ON chain_links(chain_id);
CREATE INDEX IF NOT EXISTS idx_chain_links_document_id ON chain_links(document_id);
CREATE INDEX IF NOT EXISTS idx_chain_links_link_type ON chain_links(link_type);

-- Создание представления для удобного просмотра незакрытых цепочек
CREATE OR REPLACE VIEW unclosed_chains_view AS
SELECT 
    bc.id,
    bc.contract_number,
    bc.counterparty,
    bc.total_amount,
    bc.closed_amount,
    (bc.total_amount - bc.closed_amount) as remaining_amount,
    bc.status,
    bc.created_at,
    bc.updated_at,
    EXTRACT(DAY FROM (CURRENT_DATE - bc.created_at::date)) as age_days,
    COUNT(cl.id) as documents_count,
    COUNT(CASE WHEN cl.link_type = 'contract' THEN 1 END) as contracts_count,
    COUNT(CASE WHEN cl.link_type = 'invoice' THEN 1 END) as invoices_count,
    COUNT(CASE WHEN cl.link_type = 'closing' THEN 1 END) as closing_count
FROM business_chains bc
LEFT JOIN chain_links cl ON bc.id = cl.chain_id
WHERE bc.total_amount > bc.closed_amount
GROUP BY bc.id, bc.contract_number, bc.counterparty, bc.total_amount, bc.closed_amount, bc.status, bc.created_at, bc.updated_at
ORDER BY remaining_amount DESC;

-- Создание представления для отчётов по контрагентам
CREATE OR REPLACE VIEW counterparty_reports_view AS
SELECT 
    c.id,
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
    COALESCE(SUM(CASE WHEN d.doc_type IN ('акт', 'накладная', 'счет-фактура', 'упд') THEN d.amount ELSE 0 END), 0) as closing_amount,
    COALESCE(SUM(CASE WHEN d.doc_type = 'счет' THEN d.amount ELSE 0 END), 0) - 
    COALESCE(SUM(CASE WHEN d.doc_type IN ('акт', 'накладная', 'счет-фактура', 'упд') THEN d.amount ELSE 0 END), 0) as unclosed_amount
FROM counterparties c
LEFT JOIN documents d ON c.name = d.counterparty OR c.inn = d.inn
GROUP BY c.id, c.name, c.inn, c.first_document_date, c.last_document_date, c.total_amount, c.document_count
ORDER BY c.total_amount DESC;

-- Создание функции для автоматического обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Создание триггеров для автоматического обновления updated_at
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_business_chains_updated_at BEFORE UPDATE ON business_chains
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Создание пользователя для подключения (если нужно)
-- GRANT ALL PRIVILEGES ON DATABASE doc_checker TO doc_user;
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO doc_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO doc_user;

-- Комментарии к таблицам
COMMENT ON TABLE documents IS 'Таблица для хранения информации о всех обработанных документах';
COMMENT ON TABLE counterparties IS 'Таблица для хранения информации о контрагентах с агрегированной статистикой';
COMMENT ON TABLE business_chains IS 'Таблица для хранения бизнес-цепочек (договор → счета → закрывающие документы)';
COMMENT ON TABLE chain_links IS 'Таблица связей документов в бизнес-цепочках'; 