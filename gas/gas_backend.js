/**
 * 銀河ERP - 台鐵憑證下載助手 GAS 後端
 * 
 * 系統浮水印：Falo x Force Cheng 2026/6/22
 * 
 * 部署指引：
 * 1. 瀏覽網頁 https://sheets.new 建立一個新的 Google 試算表 (Google Sheet)。
 * 2. 點選選單列的「擴充功能 (Extensions)」➔「Apps Script」進入編輯器。
 * 3. 將此檔案的所有內容複製，並貼入程式碼編輯器中（覆蓋預設的 Code.gs 內容）。
 * 4. 點選右上角「部署」->「新部署」。
 * 5. 點選左側齒輪，選擇「網頁應用程式 (Web App)」。
 * 6. 設定：
 *    - 說明：銀河ERP 台鐵憑證下載服務 (Falo x Force Cheng)
 *    - 執行身分：您的 Google 帳戶 (Me)
 *    - 誰能存取：任何人 (Anyone)
 * 7. 點選「部署」，授權存取。
 * 8. 複製產生的「網頁應用程式 URL」，將其貼入您的網頁版用戶端 (gas_client.html) 中使用。
 */

function doGet(e) {
  return handleRequest(e);
}

function doPost(e) {
  return handleRequest(e);
}

/**
 * 處理請求核心
 */
function handleRequest(e) {
  var params = e.parameter || {};
  
  // 支援 POST 傳送 JSON 格式的 Request Body
  if (e.postData && e.postData.contents) {
    try {
      var body = JSON.parse(e.postData.contents);
      params = Object.assign({}, params, body);
    } catch(err) {
      // 若不是 JSON，則保持原狀
    }
  }

  var pid = params.pid;
  var recNo = params.recNo;

  if (!pid || !recNo) {
    return makeJsonResponse({
      success: false,
      error: "缺少必要參數: pid (身分證) 或 recNo (訂票代碼)"
    });
  }

  try {
    var result = downloadTraPdf(pid, recNo);
    return makeJsonResponse(result);
  } catch (error) {
    return makeJsonResponse({
      success: false,
      error: error.message || "未知伺服器內部錯誤"
    });
  }
}

/**
 * 包裝 JSON 回傳（支援瀏覽器跨來源資源共用 CORS）
 */
function makeJsonResponse(obj) {
  var output = ContentService.createTextOutput(JSON.stringify(obj));
  output.setMimeType(ContentService.MimeType.JSON);
  return output;
}

/**
 * 三階段下載台鐵購票證明，克服 GAS 無自動 cookie 管理的問題
 */
function downloadTraPdf(pid, recNo) {
  var userAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";
  var cookies = "";

  // ==========================================
  // 步驟 1: 連線查詢頁面取得第一個 CSRF Token
  // ==========================================
  var queryUrl = "https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip115/query";
  var res1 = UrlFetchApp.fetch(queryUrl, {
    method: "get",
    headers: { "User-Agent": userAgent },
    followRedirects: true,
    muteHttpExceptions: true
  });
  
  if (res1.getResponseCode() !== 200) {
    throw new Error("無法連線至台鐵官方網站，狀態碼: " + res1.getResponseCode());
  }

  // 擷取並記錄 Cookie
  var headers1 = res1.getAllHeaders();
  cookies = mergeCookies(cookies, headers1['Set-Cookie'] || headers1['set-cookie']);

  // 用正則解析 CSRF
  var html1 = res1.getContentText();
  var csrfMatch = html1.match(/name="_csrf" value="([^"]+)"/);
  if (!csrfMatch) {
    throw new Error("解析安全標記 (CSRF 1) 失敗，請確認台鐵官方網站狀態。");
  }
  var csrfToken = csrfMatch[1];

  // ==========================================
  // 步驟 2: POST 查詢訂票紀錄
  // ==========================================
  var historyUrl = "https://tip.railway.gov.tw/tra-tip-web/tip/tip001/tip115/queryHistory";
  var payload2 = {
    "_csrf": csrfToken,
    "custIdTypeEnum": "PERSON_ID",
    "pid": pid,
    "queryMethod": "ORD_NO",
    "recNo": recNo,
    "rideDate": "",
    "startStation": "",
    "endStation": ""
  };

  var res2 = UrlFetchApp.fetch(historyUrl, {
    method: "post",
    headers: {
      "User-Agent": userAgent,
      "Cookie": cookies,
      "Referer": queryUrl,
      "Origin": "https://tip.railway.gov.tw"
    },
    payload: payload2,
    followRedirects: true,
    muteHttpExceptions: true
  });

  if (res2.getResponseCode() !== 200) {
    throw new Error("向台鐵提交查詢失敗，狀態碼: " + res2.getResponseCode());
  }

  // 擷取並合併 Cookie
  var headers2 = res2.getAllHeaders();
  cookies = mergeCookies(cookies, headers2['Set-Cookie'] || headers2['set-cookie']);

  var html2 = res2.getContentText();
  
  // 檢查是否查無紀錄
  if (html2.indexOf("無訂票記錄") !== -1 || html2.indexOf("查無訂單") !== -1 || html2.indexOf("實付金額") === -1) {
    throw new Error("台鐵伺服器查無此訂票紀錄，請確認身分證或訂票代碼。");
  }

  // ==========================================
  // 步驟 3: 解析下載連結與第二個 CSRF Token
  // ==========================================
  var actionMatch = html2.match(/action="([^"]+purchaseDownload[^"]+)"/);
  if (!actionMatch) {
    throw new Error("解析「下載購票證明」按鈕連結失敗。");
  }
  var downloadUrl = "https://tip.railway.gov.tw" + actionMatch[1];

  var afterActionHtml = html2.substring(html2.indexOf(actionMatch[0]));
  var downloadCsrfMatch = afterActionHtml.match(/name="_csrf" value="([^"]+)"/);
  var downloadCsrf = downloadCsrfMatch ? downloadCsrfMatch[1] : csrfToken;

  // ==========================================
  // 步驟 4: 下載購票證明 PDF
  // ==========================================
  var payload3 = {
    "_csrf": downloadCsrf,
    "pid": pid,
    "recNo": recNo
  };

  var res3 = UrlFetchApp.fetch(downloadUrl, {
    method: "post",
    headers: {
      "User-Agent": userAgent,
      "Cookie": cookies,
      "Referer": historyUrl,
      "Origin": "https://tip.railway.gov.tw"
    },
    payload: payload3,
    followRedirects: true,
    muteHttpExceptions: true
  });

  if (res3.getResponseCode() !== 200) {
    throw new Error("取得 PDF 串流失敗，狀態碼: " + res3.getResponseCode());
  }

  var contentType = res3.getHeaders()['Content-Type'] || res3.getHeaders()['content-type'] || "";
  var pdfBlob = res3.getBlob();
  
  // 簡單驗證是否為合格 PDF (開頭 %PDF 或是 Content-Type 為 pdf)
  var bytes = pdfBlob.getBytes();
  if (contentType.indexOf("application/pdf") === -1 && (bytes.length < 4 || (bytes[0] !== 0x25 || bytes[1] !== 0x50 || bytes[2] !== 0x44 || bytes[3] !== 0x46))) {
    throw new Error("台鐵未返回正確的 PDF 格式憑證。");
  }

  // 二進位轉為 Base64 字串以回傳給瀏覽器
  var base64Data = Utilities.base64Encode(bytes);
  return {
    success: true,
    pdfBase64: base64Data
  };
}

/**
 * 輔助函式：解析並合併 Session Cookie
 */
function mergeCookies(existingCookies, newCookieHeader) {
  if (!newCookieHeader) return existingCookies;
  
  var cookieMap = {};
  
  // 解析舊有 Cookies
  if (existingCookies) {
    var pairs = existingCookies.split(';');
    for (var i = 0; i < pairs.length; i++) {
      var pair = pairs[i].trim();
      if (!pair) continue;
      var eqIdx = pair.indexOf('=');
      if (eqIdx > 0) {
        var key = pair.substring(0, eqIdx);
        var val = pair.substring(eqIdx + 1);
        cookieMap[key] = val;
      }
    }
  }
  
  // 解析新的 Set-Cookie
  var rawCookies = [];
  if (Array.isArray(newCookieHeader)) {
    rawCookies = newCookieHeader;
  } else {
    rawCookies = [newCookieHeader];
  }
  
  for (var i = 0; i < rawCookies.length; i++) {
    var parts = rawCookies[i].split(';');
    var mainPart = parts[0].trim();
    if (!mainPart) continue;
    var eqIdx = mainPart.indexOf('=');
    if (eqIdx > 0) {
      var key = mainPart.substring(0, eqIdx);
      var val = mainPart.substring(eqIdx + 1);
      cookieMap[key] = val;
    }
  }
  
  // 重新組合 Cookie 字串
  var cookieList = [];
  for (var key in cookieMap) {
    cookieList.push(key + '=' + cookieMap[key]);
  }
  return cookieList.join('; ');
}
