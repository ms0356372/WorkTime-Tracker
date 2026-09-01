# 工時管家（WorkTime Tracker）

工時管家是以 **BeeWare Toga + SQLite** 製作的繁體中文、離線、單人手機工時管理 App。所有時數在核心與資料庫均以整數分鐘運算；不登入、不連線、不蒐集資料。本版版本為 `0.1.0`。

## 功能與架構

- 每日上下班、實際午休重疊、跨日班與基準工時計算。
- 補休優先、特休其次的可重算流水帳，以及可設定的月上限/月結規則。
- 七日疲累指數、月/年統計、五工作表 XLSX、完整 JSON 備份還原。
- `models/`、`services/`、`database/`、`views/` 與 `platform/` 分離，GUI callback 不含核心公式。
- SQLite `PRAGMA user_version` migration 與 transaction 保護寫入/還原。

> 疲累指數僅依工作時數、連續工作與休息時間估算工作負荷，不代表醫療診斷。

## 開發與執行

需要 Python 3.11+。建立環境後：

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e '.[dev]'
briefcase dev
```

執行測試與完整檢查：

```bash
pytest -q
python verify_project.py
python generate_demo_data.py
```

## Windows／Android

安裝 Python 後雙擊 `scripts/build_android.bat`，或執行 `python build_mobile.py android`。腳本會建立環境、安裝依賴、先測試，再依序執行 Briefcase create/build/package。成品會複製到 `release/android/`；報告位於 `release/build_report.txt`。Android SDK/Java 元件首次可能由 Briefcase 下載，因此需要網路與足夠磁碟空間。

## macOS／iOS

先從 App Store 安裝 Xcode 並啟動一次，再執行 `scripts/build_ios.command` 或 `python build_mobile.py ios`。腳本檢查 macOS/Xcode、測試、建立並編譯 Xcode Project，最後嘗試開啟它。**發布與真機安裝仍須在 Xcode 的 Signing & Capabilities 人工選擇 Developer Team、憑證與 Provisioning Profile**；Windows 無法產生已簽章 iOS IPA。

## 通用建置指令

`python build_mobile.py android|ios|all|test|clean`。建置會另產生 `dependency_report.txt`，並顯示 artifact 大小與 SHA256；超過可設定的 80 MB 警戒值只警告、不阻擋建置。

## 隱私、備份與限制

資料只存於裝置 SQLite。JSON 還原會取代目前資料，因此 UI 整合時必須先顯示確認。Toga 的檔案分享能力依平台版本不同，平台介面集中於 `platform/sharing.py`，後續可接 Android/iOS 原生 Share Sheet 而不影響計算核心。

## 假別扣除、轉換與稽核紀錄

「設定」可選擇 `補休優先`（預設）或 `特休優先`；資料庫使用穩定英文值 `COMP_TIME_FIRST`／`ANNUAL_LEAVE_FIRST`。假別管理可輸入整數小時與分鐘，手動進行補休與特休雙向轉換。每次轉換與撤銷都新增 MANUAL Ledger，不直接修改或刪除原交易；歷史工時重算只重建 SYSTEM 交易並重新套用人工交易。

資料庫 schema v2 採純新增欄位 migration，首次開啟舊 v1 資料庫時保留既有工作紀錄與流水帳，並補入交易日期時間、來源、類型及預設扣除順序。Excel 匯出會包含轉換的日期時間、來源與目的假別、異動、餘額及備註；若裝置無法載入 XlsxWriter，程式會使用 standard-library OOXML fallback，維持離線匯出能力。
