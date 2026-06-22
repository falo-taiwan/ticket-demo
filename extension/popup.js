// 1. 顯示/隱藏身分證功能
const pidInput = document.getElementById('pid');
const recNoInput = document.getElementById('recNo');
const filenameInput = document.getElementById('filename');
const togglePidBtn = document.getElementById('togglePidBtn');
const downloadBtn = document.getElementById('downloadBtn');
const statusDiv = document.getElementById('status');

togglePidBtn.addEventListener('click', () => {
    const isPassword = pidInput.type === 'password';
    pidInput.type = isPassword ? 'text' : 'password';
    // 切換眼球圖示 (使用行內 SVG 代替 Lucide CDN 避免被 Manifest V3 CSP 阻擋)
    togglePidBtn.innerHTML = isPassword 
        ? '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-eye-off"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.52 13.52 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/></svg>'
        : '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-eye"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>';
});

// 2. 自動聯動更新存檔名稱
recNoInput.addEventListener('input', () => {
    const code = recNoInput.value.trim();
    filenameInput.value = `TRA_Ticket_${code || '代碼'}.pdf`;
});

// 3. 核心下載邏輯
downloadBtn.addEventListener('click', async () => {
    const pid = pidInput.value.trim();
    const recNo = recNoInput.value.trim();
    const filename = filenameInput.value.trim() || `TRA_Ticket_${recNo}.pdf`;

    if (!pid || !recNo) {
        showStatus("請填寫身分證字號與訂票代碼", "error");
        return;
    }

    const originalText = downloadBtn.innerText;
    downloadBtn.disabled = true;
    downloadBtn.classList.add('loading');
    downloadBtn.innerText = "查詢下載中，請稍候...";
    showStatus("連線至台鐵官方網站...", "info");

    try {
        // 3.1. 取得第一個 CSRF Token
        const queryUrl = "https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip115/query";
        const queryRes = await fetch(queryUrl);
        if (!queryRes.ok) throw new Error(`連線失敗: ${queryRes.status}`);
        
        const htmlText = await queryRes.text();
        const csrfMatch = htmlText.match(/name="_csrf" value="([^"]+)"/);
        if (!csrfMatch) throw new Error("解析安全標記 (CSRF 1) 失敗，請確認網路或官網狀態。");
        const csrfToken = csrfMatch[1];

        // 3.2. 查詢訂票紀錄
        showStatus("正在查詢訂票紀錄...", "info");
        const historyUrl = "https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip115/queryHistory";
        const formData = new URLSearchParams();
        formData.append('_csrf', csrfToken);
        formData.append('custIdTypeEnum', 'PERSON_ID');
        formData.append('pid', pid);
        formData.append('queryMethod', 'ORD_NO');
        formData.append('recNo', recNo);
        formData.append('rideDate', '');
        formData.append('startStation', '');
        formData.append('endStation', '');

        const historyRes = await fetch(historyUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });
        if (!historyRes.ok) throw new Error(`查詢請求失敗: ${historyRes.status}`);

        const historyHtml = await historyRes.text();
        if (historyHtml.includes("無訂票記錄") || historyHtml.includes("查無訂單") || !historyHtml.includes("實付金額")) {
            throw new Error("台鐵官網回傳查無紀錄，請確認資料是否正確。");
        }

        // 3.3. 解析下載連結與第二個 CSRF Token
        showStatus("解析下載連結中...", "info");
        const downloadActionMatch = historyHtml.match(/action="([^"]+purchaseDownload[^"]+)"/);
        if (!downloadActionMatch) throw new Error("解析「下載購票證明」按鈕連結失敗。");
        
        const downloadUrl = "https://tip.railway.gov.tw" + downloadActionMatch[1];

        const afterActionHtml = historyHtml.substring(historyHtml.indexOf(downloadActionMatch[0]));
        const downloadCsrfMatch = afterActionHtml.match(/name="_csrf" value="([^"]+)"/);
        const downloadCsrf = downloadCsrfMatch ? downloadCsrfMatch[1] : csrfToken;

        // 3.4. 請求 PDF 串流
        showStatus("正在下載購票證明 PDF...", "info");
        const downloadForm = new URLSearchParams();
        downloadForm.append('_csrf', downloadCsrf);
        downloadForm.append('pid', pid);
        downloadForm.append('recNo', recNo);

        const pdfRes = await fetch(downloadUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: downloadForm
        });
        if (!pdfRes.ok) throw new Error(`下載請求失敗: ${pdfRes.status}`);

        const pdfBlob = await pdfRes.blob();
        if (pdfBlob.type !== "application/pdf" && pdfBlob.size < 1000) {
            throw new Error("取得的檔案格式不正確，可能非 PDF 串流。");
        }

        const objectUrl = URL.createObjectURL(pdfBlob);

        // 3.5. 觸發 Chrome Downloads API 下載，並套用自訂檔名
        chrome.downloads.download({
            url: objectUrl,
            filename: filename,
            conflictAction: 'uniquify'
        }, () => {
            if (chrome.runtime.lastError) {
                showStatus(`下載失敗: ${chrome.runtime.lastError.message}`, "error");
            } else {
                showStatus("✓ 購票證明已成功下載！", "success");
            }
            downloadBtn.disabled = false;
            downloadBtn.classList.remove('loading');
            downloadBtn.innerText = originalText;
        });

    } catch (error) {
        showStatus(`錯誤: ${error.message}`, "error");
        downloadBtn.disabled = false;
        downloadBtn.classList.remove('loading');
        downloadBtn.innerText = originalText;
    }
});

function showStatus(message, type) {
    statusDiv.className = type;
    statusDiv.innerText = message;
}
