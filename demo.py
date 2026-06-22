import os
import sys
import sqlite3
import json
import re
from datetime import datetime

# 嘗試導入 rich 以提供精美的終端視覺效果
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import track
    from rich import print as rprint
except ImportError:
    # 備用方案：若尚未安裝 rich，提供簡單的 print 機制
    class Console:
        def print(self, *args, **kwargs):
            print(*args)
    rprint = print
    Panel = lambda text, title="": f"=== {title} ===\n{text}\n"

console = Console()
DB_NAME = "evidence_hub.db"

# ==========================================
# 1. Evidence OCR Layer (OCR 辨識層)
# ==========================================
def run_ocr(file_path):
    """
    模擬/實作 OCR 辨識。
    如果設定了 GEMINI_API_KEY，可延伸調用 Gemini Vision API 進行 Layout-free OCR。
    本 MVP 預設使用內建的智慧解析器，可讀取文字檔並模擬 OCR 與 LLM 處理結果。
    """
    console.print(f"\n[bold cyan][Step 2/6] OCR Layer (OCR 辨識層)[/bold cyan]")
    console.print(f"正在讀取憑證檔案: [yellow]{file_path}[/yellow]")
    
    if not os.path.exists(file_path):
        console.print(f"[bold red]錯誤: 找不到憑證檔案 {file_path}[/bold red]")
        sys.exit(1)
        
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()
        
    console.print(Panel(raw_text, title="📥 憑證原始影像文字 (Raw OCR Text)"))
    
    # 模擬 AI 處理過程
    console.print("[yellow]正在運行 AI OCR / 欄位語意分析...[/yellow]")
    
    # 簡易的 Regex 提取器，模擬 OCR & LLM Extraction
    extracted_data = {}
    
    # 解析高鐵票
    if "台灣高鐵" in raw_text or "thsr" in file_path:
        train_match = re.search(r"車次:\s*([0-9]+)", raw_text)
        train_no = train_match.group(1) if train_match else ""
        extracted_data = {
            "vendor": "台灣高鐵",
            "invoice_number": re.search(r"發票號碼:\s*([A-Z0-9-]+)", raw_text).group(1) if re.search(r"發票號碼:\s*([A-Z0-9-]+)", raw_text) else "Unknown",
            "date": re.search(r"搭乘日期:\s*([0-9-]+)", raw_text).group(1) if re.search(r"搭乘日期:\s*([0-9-]+)", raw_text) else "Unknown",
            "amount": float(re.search(r"票價:\s*[^0-9]*([0-9]+)", raw_text).group(1)) if re.search(r"票價:\s*[^0-9]*([0-9]+)", raw_text) else 0.0,
            "category": "高鐵費",
            "employee_id": re.search(r"員工編號:\s*(\w+)", raw_text).group(1) if re.search(r"員工編號:\s*(\w+)", raw_text) else "EMP001",
            "description": f"出差行程: 台北 -> 左營 車次 {train_no}"
        }
    # 解析台鐵票
    elif "臺灣鐵路" in raw_text or "tra" in file_path:
        extracted_data = {
            "vendor": "臺灣鐵路",
            "invoice_number": re.search(r"證明單號:\s*([A-Za-z0-9-]+)", raw_text).group(1) if re.search(r"證明單號:\s*([A-Za-z0-9-]+)", raw_text) else "Unknown",
            "date": re.search(r"搭乘日期:\s*([0-9-]+)", raw_text).group(1) if re.search(r"搭乘日期:\s*([0-9-]+)", raw_text) else "Unknown",
            "amount": float(re.search(r"票價:\s*[^0-9]*([0-9]+)", raw_text).group(1)) if re.search(r"票價:\s*[^0-9]*([0-9]+)", raw_text) else 0.0,
            "category": "台鐵費",
            "employee_id": re.search(r"員工編號:\s*(\w+)", raw_text).group(1) if re.search(r"員工編號:\s*(\w+)", raw_text) else "EMP001",
            "description": "出差行程: 花蓮 -> 台北 太魯閣號"
        }
    else:
        # 預設 Mock 資料
        extracted_data = {
            "vendor": "未知供應商",
            "invoice_number": "ERR-99999",
            "date": datetime.today().strftime('%Y-%m-%d'),
            "amount": 100.0,
            "category": "交通費",
            "employee_id": "EMP001",
            "description": "無法辨識的票據"
        }
        
    console.print(f"[bold green]✓ OCR 辨識成功！[/bold green] 成功提取: {extracted_data['vendor']} 票券, 金額 NT$ {extracted_data['amount']}")
    return extracted_data, raw_text


# ==========================================
# 2. ETL Layer (資料轉換層)
# ==========================================
def run_etl(extracted_data, file_path):
    """
    將 OCR 提取的雜亂資料，統一對齊為企業標準的 Expense Record。
    """
    console.print(f"\n[bold cyan][Step 3/6] ETL Layer (資料轉換層)[/bold cyan]")
    console.print("[yellow]正在對齊標準 Expense Record 欄位...[/yellow]")
    
    # 進行資料清洗與補全
    # 1. 欄位補全：從資料庫查詢該員工的部門
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, department FROM employees WHERE employee_id = ?", (extracted_data['employee_id'],))
    emp_info = cursor.fetchone()
    conn.close()
    
    emp_name = emp_info[0] if emp_info else "未知員工"
    department = emp_info[1] if emp_info else "未知部門"
    
    # 2. 標準化 Expense Record
    expense_record = {
        "request_id": f"REQ-{datetime.now().strftime('%Y%m%d')}-{int(datetime.now().timestamp()) % 1000:03d}",
        "employee_id": extracted_data['employee_id'],
        "employee_name": emp_name,
        "department": department,
        "amount": extracted_data['amount'],
        "category": extracted_data['category'],
        "vendor": extracted_data['vendor'],
        "invoice_number": extracted_data['invoice_number'],
        "request_date": extracted_data['date'],
        "attachment_path": file_path,
        "source_system": "AAA-EvidenceHub-ETL",
        "description": extracted_data['description'],
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # 印出對齊後的標準 JSON
    rprint(Panel(json.dumps(expense_record, indent=2, ensure_ascii=False), title="📋 標準 Expense Record (ETL Output)"))
    return expense_record


# ==========================================
# 3. AI Audit Layer (AI 稽核與合規層)
# ==========================================
def run_audit(expense_record, raw_ocr_text):
    """
    執行稽核檢查：
    - 重複報帳檢查 (Duplicate Check)
    - 金額異常檢查 (Amount Limit Check)
    - 類別/供應商匹配檢查 (Category Mismatch Check)
    - 週末政策違規檢查 (Weekend Policy Check)
    """
    console.print(f"\n[bold cyan][Step 4/6] Audit Layer (AI 稽核層)[/bold cyan]")
    console.print("[yellow]正在啟動 AI Audit 稽核引擎，執行合規檢查...[/yellow]")
    
    audit_results = []
    has_failed = False
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. 重複報帳檢查：檢查此發票號碼是否已存在於資料庫中，且已被核銷 (POSTED 或 APPROVED)
    invoice_num = expense_record['invoice_number']
    cursor.execute(
        "SELECT request_id, employee_id, amount, status FROM expense_requests WHERE invoice_number = ? AND status IN ('APPROVED', 'POSTED')", 
        (invoice_num,)
    )
    duplicate = cursor.fetchone()
    
    if duplicate:
        audit_results.append({
            "type": "DUPLICATE",
            "result": "FAIL",
            "details": f"🚨 [重大警告] 該憑證單號/發票號碼 '{invoice_num}' 已被單號 {duplicate[0]} (員工 {duplicate[1]}, 金額 NT$ {duplicate[2]:.0f}) 核銷報支！重複報帳！"
        })
        has_failed = True
    else:
        audit_results.append({
            "type": "DUPLICATE",
            "result": "PASS",
            "details": "✓ 發票號碼重複性檢查通過 (未發現重複核銷紀錄)。"
        })
        
    # 2. 金額上限檢查 (例如：個人交通單筆大於 NT$ 1,000 需提出警告，除非有備註說明)
    amount = expense_record['amount']
    if amount > 1000.0:
        audit_results.append({
            "type": "LIMIT_EXCEEDED",
            "result": "WARNING",
            "details": f"⚠️ [警告] 單筆交通費 NT$ {amount:,.0f} 超過一般額度限制 (NT$ 1,000)。需會計覆核其出差合理性。"
        })
    else:
        audit_results.append({
            "type": "LIMIT_EXCEEDED",
            "result": "PASS",
            "details": f"✓ 報支金額 NT$ {amount:,.0f} 在政策規定標準內。"
        })
        
    # 3. 類別與供應商匹配檢查 (防弊)
    category = expense_record['category']
    vendor = expense_record['vendor']
    if category == "高鐵費" and "臺灣鐵路" in vendor:
        audit_results.append({
            "type": "CATEGORY_MISMATCH",
            "result": "FAIL",
            "details": f"❌ [不合規] 申報費用類別為 '{category}'，但發票憑證實際供應商為 '{vendor}'，類別申報錯誤！"
        })
        has_failed = True
    else:
        audit_results.append({
            "type": "CATEGORY_MISMATCH",
            "result": "PASS",
            "details": f"✓ 費用類別 '{category}' 與憑證供應商 '{vendor}' 一致。"
        })

    # 4. 週末乘車檢查 (週末出差若無事由說明則警告)
    date_str = expense_record['request_date']
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # 0=Monday, 5=Saturday, 6=Sunday
        if dt.weekday() in [5, 6]:
            audit_results.append({
                "type": "POLICY_VIOLATION",
                "result": "WARNING",
                "details": f"⚠️ [警告] 乘車日期 {date_str} 為週末，請確認該行程是否屬於公務加班出差。"
            })
        else:
            audit_results.append({
                "type": "POLICY_VIOLATION",
                "result": "PASS",
                "details": f"✓ 乘車日期 {date_str} 為工作日。"
            })
    except Exception:
        pass

    conn.close()
    
    # 輸出稽核報告表格
    table = Table(title="🛡️ AI Audit 稽核報告")
    table.add_column("檢核項目", style="cyan")
    table.add_column("結果", style="magenta")
    table.add_column("稽核詳細內容說明", style="green")
    
    for r in audit_results:
        res_text = Text(r['result'])
        if r['result'] == 'PASS':
            res_text.stylize("bold green")
        elif r['result'] == 'WARNING':
            res_text.stylize("bold yellow")
        else:
            res_text.stylize("bold red")
        table.add_row(r['type'], res_text, r['details'])
        
    console.print(table)
    
    status = "REJECTED" if has_failed else "AUDITED"
    return audit_results, status


# ==========================================
# 4. Workflow Layer (工作流狀態機)
# ==========================================
def run_workflow_and_erp(expense_record, audit_results, final_status):
    """
    控制簽核生命週期，並寫入 SQLite (模擬天心 ERP)。
    """
    console.print(f"\n[bold cyan][Step 5/6] Workflow & ERP Layer (流程與 ERP 入帳層)[/bold cyan]")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    req_id = expense_record['request_id']
    emp_id = expense_record['employee_id']
    
    # 1. 寫入報支單主檔
    console.print(f"正在將報支單 [cyan]{req_id}[/cyan] 寫入模擬 ERP 主檔...")
    cursor.execute(
        """
        INSERT INTO expense_requests (request_id, employee_id, request_date, amount, category, vendor, invoice_number, status, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            req_id,
            emp_id,
            expense_record['request_date'],
            expense_record['amount'],
            expense_record['category'],
            expense_record['vendor'],
            expense_record['invoice_number'],
            "SUBMITTED", # 初始送審狀態
            expense_record['description']
        )
    )
    
    # 2. 寫入附件與 OCR 文本
    cursor.execute(
        """
        INSERT INTO expense_attachments (request_id, file_name, file_path, file_type, raw_ocr_text)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            req_id,
            os.path.basename(expense_record['attachment_path']),
            expense_record['attachment_path'],
            "txt",
            expense_record['description']
        )
    )
    
    # 3. 寫入 Workflow 歷史軌跡
    cursor.execute(
        "INSERT INTO workflow_log (request_id, action, operator, previous_status, new_status, comment) VALUES (?, ?, ?, ?, ?, ?)",
        (req_id, "SUBMIT", f"EMP001_{expense_record['employee_name']}", "DRAFT", "SUBMITTED", "電子憑證自動上傳並轉入報支")
    )
    
    # 4. 根據 AI Audit 結果進行自動化簽核分流
    if final_status == "REJECTED":
        console.print(f"[bold red]❌ AI Audit 檢出致命合規警告！工作流自動執行 [退件 (REJECTED)]。[/bold red]")
        cursor.execute(
            "UPDATE expense_requests SET status = 'REJECTED' WHERE request_id = ?", (req_id,)
        )
        cursor.execute(
            "INSERT INTO workflow_log (request_id, action, operator, previous_status, new_status, comment) VALUES (?, ?, ?, ?, ?, ?)",
            (req_id, "REJECT", "SYSTEM_AI_AUDITOR", "SUBMITTED", "REJECTED", "AI Audit 偵測到重複報帳或嚴重合規問題，自動予以退回。")
        )
    else:
        console.print(f"[bold green]✓ AI Audit 基礎合規通過。進入審批流：主管李大同核准 -> 會計林美美入帳...[/bold green]")
        
        # 模擬主管核准 (APPROVED)
        cursor.execute(
            "UPDATE expense_requests SET status = 'APPROVED' WHERE request_id = ?", (req_id,)
        )
        cursor.execute(
            "INSERT INTO workflow_log (request_id, action, operator, previous_status, new_status, comment) VALUES (?, ?, ?, ?, ?, ?)",
            (req_id, "APPROVE", "EMP002_李大同_MANAGER", "SUBMITTED", "APPROVED", "AI 預審通過，予以核准。")
        )
        
        # 模擬會計覆核並 ERP 入帳 (POSTED)
        cursor.execute(
            "UPDATE expense_requests SET status = 'POSTED' WHERE request_id = ?", (req_id,)
        )
        cursor.execute(
            "INSERT INTO workflow_log (request_id, action, operator, previous_status, new_status, comment) VALUES (?, ?, ?, ?, ?, ?)",
            (req_id, "POST", "EMP003_林美美_ACCOUNTANT", "APPROVED", "POSTED", "確認發票憑證無誤，ERP 完成傳票立帳入帳。")
        )
        
    # 5. 寫入 Audit Log 到資料庫備查
    for audit in audit_results:
        cursor.execute(
            "INSERT INTO audit_log (request_id, audit_type, result, details) VALUES (?, ?, ?, ?)",
            (req_id, audit['type'], audit['result'], audit['details'])
        )
        
    conn.commit()
    conn.close()
    console.print(f"[bold green]✓ Workflow 工作流執行與 ERP 狀態更新完成。[/bold green]")


# ==========================================
# 5. Dashboard / Verification (ERP 狀態檢視)
# ==========================================
def show_erp_summary():
    """
    讀取 SQLite 資料庫，輸出當前的報支單狀態與 Audit Log。
    """
    console.print(f"\n[bold cyan][Step 6/6] Database Verification (模擬 ERP 最終狀態查詢)[/bold cyan]")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT r.request_id, e.name, r.amount, r.category, r.invoice_number, r.status, r.description 
        FROM expense_requests r
        JOIN employees e ON r.employee_id = e.employee_id
        ORDER BY r.created_at DESC
    """)
    records = cursor.fetchall()
    
    table = Table(title="天心 ERP 模擬報支單列表")
    table.add_column("報支單號", style="cyan")
    table.add_column("員工", style="magenta")
    table.add_column("金額", style="yellow")
    table.add_column("類別", style="green")
    table.add_column("憑證編號", style="blue")
    table.add_column("簽核狀態", style="red")
    table.add_column("事由/備註說明", style="white")
    
    for r in records:
        status_style = "bold red" if r[5] == "REJECTED" else "bold green" if r[5] == "POSTED" else "yellow"
        table.add_row(r[0], r[1], f"NT$ {r[2]:,.0f}", r[3], r[4], Text(r[5], style=status_style), r[6])
        
    console.print(table)
    
    # 顯示稽核日誌
    cursor.execute("SELECT request_id, audit_type, result, details FROM audit_log ORDER BY created_at DESC LIMIT 5")
    audits = cursor.fetchall()
    
    table_audit = Table(title="系統稽核日誌備查檔 (audit_log)")
    table_audit.add_column("單號", style="cyan")
    table_audit.add_column("檢核項目", style="magenta")
    table_audit.add_column("結果", style="yellow")
    table_audit.add_column("警示詳情", style="green")
    
    for a in audits:
        res_style = "bold green" if a[2] == "PASS" else "bold yellow" if a[2] == "WARNING" else "bold red"
        table_audit.add_row(a[0], a[1], Text(a[2], style=res_style), a[3])
        
    console.print(table_audit)
    conn.close()


# ==========================================
# 6. 一鍵 Demo 主程式入口
# ==========================================
def main():
    if not os.path.exists(DB_NAME):
        console.print(f"[bold red]錯誤: 找不到資料庫 {DB_NAME}，請先執行 `python3 setup_db.py` 進行初始化。[/bold red]")
        sys.exit(1)
        
    console.print(Panel.fit(
        "   AAA-Evidence Hub - 企業電子憑證自動化處理 PoC 平台   \n"
        "   天心 ERP Class04 課程專用展示實作程式 (MVP)   ",
        style="bold magenta"
    ))
    
    # 提供選單給課堂操作
    console.print("請選擇要處理的模擬憑證來源檔案：")
    console.print("  [1] 高鐵票證明 (thsr_ticket.txt) -> [bold red]測試重複報支情境 (會被退件)[/bold red]")
    console.print("  [2] 台鐵購票證明 (tra_ticket.txt) -> [bold green]測試正常報支與入帳情境[/bold green]")
    
    choice = input("\n請輸入選擇 (1 或 2): ").strip()
    
    if choice == "1":
        file_path = "mock_evidence/thsr_ticket.txt"
    elif choice == "2":
        file_path = "mock_evidence/tra_ticket.txt"
    else:
        console.print("[bold red]無效的選擇，預設執行台鐵憑證流程。[/bold red]")
        file_path = "mock_evidence/tra_ticket.txt"
        
    # 執行流程
    extracted_data, raw_ocr = run_ocr(file_path)
    expense_record = run_etl(extracted_data, file_path)
    audit_results, status = run_audit(expense_record, raw_ocr)
    run_workflow_and_erp(expense_record, audit_results, status)
    show_erp_summary()
    
    console.print("\n[bold green]🏁 AAA-Evidence Hub 完整工作流示範結束。[/bold green]")

if __name__ == "__main__":
    main()
