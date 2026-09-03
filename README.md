# 工時管家（WorkTime Tracker）

工時管家是以 **BeeWare Toga + SQLite** 製作的繁體中文、單人手機工時管理 App。所有時數在核心與資料庫均以整數分鐘運算；不登入、不蒐集資料，只有更新官方國定假日快取時使用網路。本版版本為 `0.8.0`。

v0.8.0 新增工作日曆：平日、官方國定假日與使用者特殊日期覆寫共用同一套判斷；從工時計算起始日起，已過且未登錄的正常上班日會納入假別不足計算，今天及未來日期不會預扣。

## 功能與架構

- 首頁可依特休結算日所定義的「今年度」或全部紀錄匯出人類可閱讀的 `.xlsx` 報表。
- 設定頁提供版本化 `.worktimebackup` 完整備份與安全還原；Excel 僅供報表使用，不能作為還原來源。
- Android 匯出與備份使用系統檔案選擇器，不要求所有檔案存取權或傳統外部儲存權限。
- Android 系統 Auto Backup/Auto Restore 已停用；一般覆蓋升級仍保留本機 SQLite，解除安裝後的資料移轉則使用 `.worktimebackup`。

- 每日上下班、實際午休重疊、跨日班與基準工時計算。
- 補休優先、特休其次的可重算流水帳，以及可設定的月上限/月結規則。
- 七日疲累指數、月/年統計、四工作表 XLSX、版本化完整備份還原。
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

在 **Windows 10/11** 安裝 Python 3.11+（安裝時勾選 `Add Python to PATH`）後，可直接雙擊專案根目錄的 `build_android.bat`；它會轉交給 `scripts/build_android.bat`。也可以在 PowerShell 執行 `python build_mobile.py android`。

腳本不是只建立設定：它會建立 `.venv`、安裝依賴、執行全部測試，再依序執行 Briefcase `create android`、`build android`、`package android`，因此完成後會自動得到可發布的 Android artifact。成品會複製到 `release/android/`，報告位於 `release/build_report.txt`，完整終端紀錄則永久保存在 `release/build_android.log`。

首次建置需要下載 Briefcase、Android SDK、Gradle 與 Android 支援套件，通常需要 10–30 分鐘；某些下載階段可能數分鐘沒有新文字，但視窗不應關閉。成功或失敗後腳本都會停在「按任意鍵」畫面。若雙擊完全沒有視窗，請確認是在 Windows 執行、檔案不是從 ZIP 內直接開啟，然後在專案資料夾開啟 PowerShell 執行 `cmd /k build_android.bat`，即可看到 Windows 阻擋或 Python PATH 等錯誤。

## macOS／iOS

先從 App Store 安裝 Xcode 並啟動一次，再執行 `scripts/build_ios.command` 或 `python build_mobile.py ios`。腳本檢查 macOS/Xcode、測試、建立並編譯 Xcode Project，最後嘗試開啟它。**發布與真機安裝仍須在 Xcode 的 Signing & Capabilities 人工選擇 Developer Team、憑證與 Provisioning Profile**；Windows 無法產生已簽章 iOS IPA。

## 通用建置指令

`python build_mobile.py android|ios|all|test|clean|doctor`，Android 另支援 `python build_mobile.py android --clean`。建置會另產生 `dependency_report.txt`，並顯示 artifact 大小與 SHA256；超過可設定的 80 MB 警戒值只警告、不阻擋建置。

## 隱私、備份與限制

資料只存於裝置 SQLite。JSON 還原會取代目前資料，因此 UI 整合時必須先顯示確認。Toga 的檔案分享能力依平台版本不同，平台介面集中於 `platform/sharing.py`，後續可接 Android/iOS 原生 Share Sheet 而不影響計算核心。

## 假別扣除、轉換與稽核紀錄

「設定」可選擇 `補休優先`（預設）或 `特休優先`；資料庫使用穩定英文值 `COMP_TIME_FIRST`／`ANNUAL_LEAVE_FIRST`。假別管理可輸入整數小時與分鐘，手動進行補休與特休雙向轉換。每次轉換與撤銷都新增 MANUAL Ledger，不直接修改或刪除原交易；歷史工時重算只重建 SYSTEM 交易並重新套用人工交易。

資料庫 schema v2 採純新增欄位 migration，首次開啟舊 v1 資料庫時保留既有工作紀錄與流水帳，並補入交易日期時間、來源、類型及預設扣除順序。Excel 匯出會包含轉換的日期時間、來源與目的假別、異動、餘額及備註；若裝置無法載入 XlsxWriter，程式會使用 standard-library OOXML fallback，維持離線匯出能力。

### Android 環境診斷與乾淨重建

打包前可在專案虛擬環境執行 `python build_mobile.py doctor`。診斷會列出實際 Python、Briefcase 版本、Java、Android SDK 環境變數、Briefcase 設定、既有 scaffold 與 release 目錄。未設定 `JAVA_HOME` 或 `ANDROID_HOME` 只會提示，不會直接判定失敗，因為 Briefcase 可以準備隔離的 Android 工具；若使用系統 JDK，應安裝 Java 17。

`python build_mobile.py android` 採 incremental build：找不到 Android Gradle scaffold 時才執行一次 `briefcase create android`，後續改用 `briefcase update android`。需要刻意刪除 Android scaffold/cache 並重建時，使用 `python build_mobile.py android --clean`。APK 一律透過 `briefcase package android -p apk` 產生，再遞迴尋找新 APK，複製為 `release/android/工時管家-0.8.0-release.apk` 或 `工時管家-0.8.0-debug.apk`；即時輸出也會保存於 `release/build_android.log`。

Windows 雙擊 `build_android.bat` 只會執行檢查與 Debug APK 建置，不會呼叫 ADB、安裝 APK 或清除手機資料。

### `BackendUnavailable` 修復

若舊版專案曾顯示 `Cannot import 'briefcase.integrations.setuptools'`，新版已改用標準 `setuptools.build_meta` editable-install backend。Android BAT 會先升級 `pip`、`setuptools`、`wheel`，再安裝 Briefcase，最後才執行 `pip install -e ".[dev]"`。既有 `.venv` 可直接再次執行 `build_android.bat` 進行修復；若該環境曾中途損壞，可刪除 `.venv` 後重新雙擊 BAT。
