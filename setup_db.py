import sqlite3
import os
from rich.console import Console
from rich.table import Table

console = Console()

DB_NAME = "evidence_hub.db"
SCHEMA_FILE = "schema.sql"

def setup_database():
    console.print(f"[bold blue]開始建置模擬 ERP 資料庫: {DB_NAME}...[/bold blue]")
    
    # 1. 讀取並執行 Schema
    if not os.path.exists(SCHEMA_FILE):
        console.print(f"[bold red]錯誤: 找不到 {SCHEMA_FILE}！[/bold red]")
        return
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_script = f.read()
        
    try:
        cursor.executescript(schema_script)
        conn.commit()
        console.print("[bold green]✓ 資料庫表格建立成功！[/bold green]")
    except Exception as e:
        console.print(f"[bold red]資料庫建立失敗: {e}[/bold red]")
        conn.close()
        return

    # 2. 插入測試用基礎資料
    console.print("[yellow]正在寫入模擬基礎資料...[/yellow]")
    
    # 2.1 員工資料 (employees)
    employees_data = [
        ("EMP001", "張小明", "資訊研發部", "xiaoming.zhang@falo.com"),
        ("EMP002", "李大同", "資訊部經理", "datong.li@falo.com"),
        ("EMP003", "林美美", "財務會計部", "meimei.lin@falo.com"),
    ]
    cursor.executemany(
        "INSERT OR REPLACE INTO employees (employee_id, name, department, email) VALUES (?, ?, ?, ?)",
        employees_data
    )

    # 2.2 歷史已報支資料 (用於觸發 AI Audit 稽核檢查)
    # 我們先寫入一個已經核銷過的高鐵票號 'EB-87654321'，等等 Demo 上傳同一個高鐵票時，就能觸發「重複報帳」警告！
    historical_requests = [
        ("REQ-20260601-098", "EMP001", "2026-06-01", 1490.0, "高鐵費", "台灣高鐵", "EB-87654321", "POSTED", "6/15 台北至左營研討會出差 (已入帳)", "2026-06-01 10:00:00"),
        ("REQ-20260610-011", "EMP001", "2026-06-10", 3500.0, "計程車費", "大都會車隊", "TAX-9988221", "POSTED", "拜訪南部重要客戶", "2026-06-10 17:30:00"),
    ]
    cursor.executemany(
        "INSERT OR REPLACE INTO expense_requests (request_id, employee_id, request_date, amount, category, vendor, invoice_number, status, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        historical_requests
    )

    # 2.3 寫入歷史附件關聯
    historical_attachments = [
        (1, "REQ-20260601-098", "thsr_ticket_old.txt", "mock_evidence/thsr_ticket.txt", "txt", "台灣高鐵 乘車票證明 發票號碼: EB-87654321"),
    ]
    cursor.executemany(
        "INSERT OR REPLACE INTO expense_attachments (attachment_id, request_id, file_name, file_path, file_type, raw_ocr_text) VALUES (?, ?, ?, ?, ?, ?)",
        historical_attachments
    )

    conn.commit()
    conn.close()
    console.print("[bold green]✓ 模擬資料寫入完成！[/bold green]\n")
    
    show_db_status()

def show_db_status():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 印出員工資料
    cursor.execute("SELECT * FROM employees")
    employees = cursor.fetchall()
    
    table_emp = Table(title="模擬 ERP 員工清單 (employees)")
    table_emp.add_column("員工編號", style="cyan")
    table_emp.add_column("姓名", style="magenta")
    table_emp.add_column("部門", style="green")
    table_emp.add_column("Email", style="blue")
    
    for emp in employees:
        table_emp.add_row(emp[0], emp[1], emp[2], emp[3])
        
    console.print(table_emp)
    console.print()
    
    # 印出歷史報支
    cursor.execute("SELECT request_id, employee_id, amount, category, invoice_number, status FROM expense_requests")
    reqs = cursor.fetchall()
    
    table_req = Table(title="模擬 ERP 歷史報支主檔 (expense_requests)")
    table_req.add_column("申請單號", style="cyan")
    table_req.add_column("員工編號", style="magenta")
    table_req.add_column("金額", style="yellow")
    table_req.add_column("類別", style="green")
    table_req.add_column("憑證單號", style="blue")
    table_req.add_column("狀態", style="red")
    
    for r in reqs:
        table_req.add_row(r[0], r[1], f"NT$ {r[2]:,.0f}", r[3], r[4], r[5])
        
    console.print(table_req)
    conn.close()

if __name__ == "__main__":
    setup_database()
