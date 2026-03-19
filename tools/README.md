# 🛠️ 工具腳本說明

本目錄包含用於數據處理和下載的 Python 工具腳本。

## 📝 腳本列表

### 1. convert_taiwan_lottery_csv.py
**功能**：轉換台灣彩券官方 CSV 格式為系統可用格式

**使用方法**：
```bash
python3 convert_taiwan_lottery_csv.py
```

**輸入格式**：台灣彩券官方 CSV（包含遊戲名稱、銷售額等完整資訊）
**輸出格式**：簡化 CSV（期數、日期、號碼1-6、特別號）

---

### 2. generate_realistic_data.py
**功能**：生成模擬的大樂透數據用於測試

**使用方法**：
```bash
python3 generate_realistic_data.py
```

**輸出**：生成符合真實分佈的模擬數據

---

### 3. download_lottery_data.py
**功能**：從台灣彩券官網下載歷史數據

**使用方法**：
```bash
python3 download_lottery_data.py
```

**注意**：需要網路連線

---

### 4. scrape_lottery_data.py
**功能**：爬取台灣彩券網站的開獎數據

**使用方法**：
```bash
python3 scrape_lottery_data.py
```

**依賴**：可能需要安裝 requests、beautifulsoup4 等套件

---

### 5. universal_downloader.py
**功能**：通用的數據下載器

**使用方法**：
```bash
python3 universal_downloader.py
```

---

## 📦 依賴套件

部分腳本可能需要以下 Python 套件：

```bash
pip3 install requests beautifulsoup4 pandas
```

## ⚠️ 注意事項

1. 這些工具主要用於開發和測試
2. 下載工具可能因網站結構變更而失效
3. 請遵守台灣彩券網站的使用條款
4. 建議使用虛擬環境運行這些腳本

## 💡 提示

如果您只是想使用分析系統，不需要運行這些工具。系統已內建範例數據功能。
