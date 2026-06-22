-- =======================================================
-- AAA-Evidence Hub: Database Schema for SQLite
-- Description: Core tables to support Evidence, OCR, ETL, Workflow, ERP and Audit Layer
-- =======================================================

DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS workflow_log;
DROP TABLE IF EXISTS expense_attachments;
DROP TABLE IF EXISTS expense_requests;
DROP TABLE IF EXISTS employees;

-- 1. 員工基本資料表 (employees)
CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 報支申請主檔 (expense_requests)
CREATE TABLE IF NOT EXISTS expense_requests (
    request_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    request_date TEXT NOT NULL,          -- 報支申請日期 (YYYY-MM-DD)
    amount REAL NOT NULL,                -- 報支金額
    category TEXT NOT NULL,              -- 費用類別 (e.g., 高鐵費, 台鐵費, 計程車費, 停車費)
    vendor TEXT,                         -- 供應商/商戶 (e.g., 台灣高鐵, 臺灣鐵路)
    invoice_number TEXT,                 -- 發票/憑證單號
    status TEXT DEFAULT 'DRAFT',         -- 狀態: DRAFT (草稿), SUBMITTED (送審), APPROVED (主管同意), AUDITED (AI稽核完成), REJECTED (退件), POSTED (ERP入帳)
    description TEXT,                    -- 說明/用途備註
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
);

-- 3. 憑證附件表 (expense_attachments)
CREATE TABLE IF NOT EXISTS expense_attachments (
    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,                      -- e.g., pdf, png, txt
    raw_ocr_text TEXT,                   -- OCR 識別出的原始文本內容，提供 AI Audit 分析
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES expense_requests(request_id)
);

-- 4. 簽核工作流日誌 (workflow_log)
CREATE TABLE IF NOT EXISTS workflow_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    action TEXT NOT NULL,                -- 動作: SUBMIT (送審), APPROVE (核准), REJECT (退回), AUDIT (稽核), POST (入帳)
    operator TEXT NOT NULL,              -- 執行人 (如 EMP002_MANAGER, SYSTEM_AI, EMP003_ACCOUNTANT)
    previous_status TEXT,
    new_status TEXT,
    comment TEXT,                        -- 簽核意見/原因
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES expense_requests(request_id)
);

-- 5. AI 與人工稽核日誌 (audit_log)
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    audit_type TEXT NOT NULL,            -- 稽核類型: DUPLICATE (重複報帳), LIMIT_EXCEEDED (超額異常), CATEGORY_MISMATCH (類別錯誤), ATTACHMENT_MISSING (缺少附件), POLICY_VIOLATION (政策違規)
    result TEXT NOT NULL,                -- 稽核結果: PASS (通過), WARNING (警告), FAIL (不通過)
    details TEXT,                        -- 具體原因與AI稽核回饋
    auditor TEXT DEFAULT 'AI_AUDIT_AGENT',-- 審核者 (AI_AUDIT_AGENT / HUMAN_AUDITOR)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(request_id) REFERENCES expense_requests(request_id)
);
