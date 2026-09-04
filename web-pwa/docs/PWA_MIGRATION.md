# WorkTime Tracker PWA Migration（Phase 3）

## Phase 3 implementation status

| Capability | Status | Notes |
|---|---|---|
| Daily standard minutes | IMPLEMENTED | IndexedDB setting `daily_standard_minutes`; integer minutes only. Existing records retain their stored snapshot. |
| Lunch range | IMPLEMENTED | `lunch_break_start` / `lunch_break_end`; new record flows consume these values and overlap calculation remains minute based. |
| Calculation start | IMPLEMENTED | `work_tracking_start_date`; required/missing analysis excludes earlier dates. An absent setting initializes to the local current date, matching Python migration safety. |
| Calendar priority | IMPLEMENTED | Special override > official holiday > Monday–Friday/weekend. |
| Special dates | IMPLEMENTED | IndexedDB upsert by unique date, list and delete UI. |
| Official holiday repository/cache | IMPLEMENTED | Query/get and atomic replace-year import persist offline in IndexedDB. |
| Official holiday network sync | PARTIAL | Browser network/CORS sync is intentionally not claimed; Settings offers explicit JSON annual import/update and keeps the last successful cache. |
| Calendar month classification | IMPLEMENTED | Each date shows work/non-work classification, source label/note, and recorded minutes. |
| Monthly analysis | IMPLEMENTED | Month navigation, total/attendance/rounded average/overtime/shortfall/holiday work/scheduled/missing counts. Future/today dates are not missing. |
| Ledger, leave deduction and leave balances | NOT IMPLEMENTED | Analysis does not deduct comp or annual leave and the dashboard hides fabricated balances. |
| Cloud/Auth/Supabase, export, backup/restore | NOT IMPLEMENTED | Explicitly outside Phase 3. |
| Windows local scripts | IMPLEMENTED | `verify_pwa.bat` checks tools, installs, tests, builds and validates output; run/build-only scripts fail fast. |

Missing-workday safety follows Python: a normal weekday is only marked missing when that year has official-holiday cache; an explicit special-date override is independently authoritative. This avoids charging a weekday that may actually be a holiday. Attendance counts only records with positive calculated minutes, and average uses Python-compatible integer rounding (`Math.round`, equivalent for non-negative minute values).

> 分析基準：Python/Android `0.8.5` source、tests 與本任務實機截圖。PWA 採整數分鐘、offline-first；本文件的 **DONE 僅表示本階段確實完成的 foundation**，不把靜態畫面誤稱為功能完成。

## 1. Existing app inventory

### 實際模型、SQLite 與 repository

- Domain model：`WorkRecord`、`LedgerEntry`、`LeaveCycle`；enum 包含 `WorkdayType`、`LeaveType`、`DeductionPriority`、`TransactionType`、`LedgerOrigin`。所有 duration/balance 為 integer minutes。
- SQLite schema v5：`work_records`（`work_date` UNIQUE）、`settings`、`leave_cycles`、`balance_ledger`、`monthly_settlements`、`app_metadata`、`calendar_overrides`、`official_holidays`、`comp_leave_cycles`、`comp_settlement_policy_history`、`comp_monthly_settlements`。
- Repository：`WorkRecordRepository`（同日 save 為 update、month range、recent、CRUD）、`SettingsRepository`（含 lunch、priority、tracking start、comp policy history）、`CalendarOverrideRepository`、`OfficialHolidayRepository`、`LedgerRepository`、`LeaveCycleRepository`。

### Services 與規則盤點

| 領域 | 現有 Python 行為 | 現況 |
|---|---|---|
| 紀錄 | 同一天一筆；save upsert，update 保持原日期，delete 後 deterministic rebuild ledger | IMPLEMENTED |
| 工時計算 | `clock_out - clock_in`；只有明確 `overnight` 才跨日；午休只扣 `[clock-in, clock-out]` 與設定午休區間 overlap；結果、標準、差額皆分鐘 | IMPLEMENTED |
| 工時差額 | `actual - calendar.standard_minutes_for(day)`；正值補休、負值依 priority 扣假 | IMPLEMENTED |
| 漏登 | tracking start 起至 yesterday；只對有可靠假日資料（或 override）的正常工作日建立不足 | IMPLEMENTED |
| 工作日曆 | override 優先；其次 official holiday；再其次 Mon–Fri；WORKDAY override 可將假日/週末變工作日，NON_WORKDAY 可將平日變休假 | IMPLEMENTED |
| 國定假日 | 內建 2026/2027 fallback；政府 open-data metadata 選年度 CSV、解析、驗證、cache、7 日 freshness | IMPLEMENTED（Web CORS 尚待驗證） |
| 分析 | 月/年 summary：總分鐘、紀錄出勤日、floor 平均、超時、不足、假日工時；含漏登時按 calendar 補不足 | IMPLEMENTED |
| 年度特休 | settlement 日為 cycle 最後日；期間是上次結算日隔天至本次/下次結算日；2/29 在非閏年 clamp 2/28；cycle grant/settlement ledger | IMPLEMENTED |
| 補休 | 分 monthly/annual buckets；monthly 模式先累積月補休，使用時先扣月補休；月底依 cap 轉年度，超額折現；年度結算歸零 | IMPLEMENTED |
| 折現 | cents 儲存；`cash_minutes × hourly_rate_cents / 60` 依 Python engine 的整數規則產生 `cash_amount_cents`，不可用浮點小時 | IMPLEMENTED |
| Ledger | system events 可由 source records/cycles/policies 重建；manual conversion/reversal 保存；balance snapshot 含 total、monthly、annual comp | IMPLEMENTED |
| 轉換 | Comp ↔ Annual，預設 1:1 `Fraction`；不足/零/同類拒絕；撤銷新增 REVERSAL 並以 `reversal_of_id` 關聯，不 destructive delete | IMPLEMENTED |
| Excel | `.xlsx`，每日紀錄、統計摘要、假別資料、設定摘要、補休結算共五 sheet；支援 all/leave-year | IMPLEMENTED |
| Backup/restore | transaction-safe restore、還原前安全備份、checksum、schema/format validation、重建 system ledger | IMPLEMENTED |
| 疲累指數 | service/test 尚存在，但最新 UI/需求不以此為核心；PWA 刻意不移植 | NOT IMPLEMENTED（by design） |
| PWA CRUD / ledger / export / restore | Phase 3 已接 WorkRecord CRUD；ledger/export/restore 尚未實作 | PARTIAL |

## 2. Ledger、結算與分析細節

1. `TransactionType` 完整事件集合：work earn/deduction、missing-workday deduction、monthly settlement、annual grant/settlement、comp annual settlement、comp monthly transfer/cash、conversion、reversal、adjustment。
2. Ledger 是 audit event，不是單一 balance 欄位。每一事件保留 changes、balance-after、來源紀錄、來源/目的假別、transaction/created timestamps、origin、reversal link，以及 monthly/annual comp snapshots。
3. 不足扣除尊重 `COMP_TIME_FIRST` 或 `ANNUAL_LEAVE_FIRST`；餘額不足的未覆蓋分鐘仍是 shortfall，不能製造負假別餘額。
4. Monthly comp policy 具 `effective_from` history。月底 `pre_monthly_balance` 在 cap 內轉入 annual bucket；超過 cap 為 cash minutes；折現金額全程 cents/integer arithmetic。`comp_monthly_settlements` 保存 before/after、cap、transfer、cash、rate、amount 與同月是否年度結算。
5. 月分析只選該 calendar month。年分析以 UI 所選月份的 `year`，不可固定 today.year。平均為總分鐘除出勤日並依 Python `round` 取整數；假日/休息日實作依 calendar standard=0，因此工作分鐘列假日工作與 overtime。

## 3. Migration matrix

| Python component | PWA component | Migration status | Notes |
|---|---|---|---|
| SQLite schema v5 | `db/database.ts` Dexie schema v1 | IN PROGRESS | stores/indexes 已規劃；資料 migration 尚未實作 |
| `WorkRecord`, enums | `models/domain.ts` | DONE | ISO local date/time + integer minutes |
| `LedgerEntry`, cycles | `models/domain.ts` | DONE | model skeleton 完整保留 audit fields |
| WorkRecordRepository | contract + `DexieWorkRecordRepository` | IMPLEMENTED | upsert/query/delete 與 basic UI 已接；ledger transaction 尚未實作 |
| SettingsRepository | contract + Dexie adapter | IMPLEMENTED | standard minutes、lunch 與 tracking start 已接 UI |
| LedgerRepository | contract + Dexie adapter | IN PROGRESS | append/read skeleton；重建 engine 未移植 |
| Calendar/holiday repositories | contracts + Dexie adapters | IMPLEMENTED | override CRUD、holiday annual cache replace/query；network sync PARTIAL |
| Worktime calculator | `services/workTimeService.ts` | IN PROGRESS | basic/overnight/lunch overlap 已移植與測試 |
| AnalyticsService | `services/analysisService.ts` | IMPLEMENTED | Phase 3 monthly metrics/missing/holiday work；cycle balances out of scope |
| Balance/settlement service | future services | NOT STARTED | 下一階段依 Python tests parity 移植 |
| LeaveConversionService | future service | NOT STARTED | 必須保留 append-only reversal |
| BackupService | future backup feature | NOT STARTED | mapping 已列於下節 |
| ExcelExportService | future export feature | NOT STARTED | 五 sheet parity；依賴評估後再選 library |
| WorkCalendarService | `services/calendarService.ts` | IMPLEMENTED | priority and local-date classification; network sync remains PARTIAL |
| DashboardView | `HomePage.tsx` | IMPLEMENTED | IndexedDB-backed Phase 3 month metrics |
| RecordsView | `RecordsPage.tsx` | IMPLEMENTED | IndexedDB upsert/recent/delete with settings snapshots |
| MonthlyRecordsView | `CalendarPage.tsx` | IMPLEMENTED | month navigation and per-date calendar/record classification |
| AnalysisView | `AnalysisPage.tsx` | IMPLEMENTED | Phase 3 monthly metrics backed by repositories/services |
| SettingsView | `SettingsPage.tsx` | IMPLEMENTED | Phase 3 settings, overrides and holiday import |

## 4. Android backup → PWA mapping plan

Android `.worktimebackup` 是 ZIP：`manifest.json` + `data.json`。manifest format=`WorkTimeTrackerBackup`、目前 format version=2，帶 app version、created timestamp、SQLite schema version、record count、`data.json` SHA-256。PWA importer 應先在記憶體驗證 ZIP、UTF-8 JSON、checksum、allow-listed columns、必填欄位、唯一日期，再以單一 Dexie transaction 寫入；失敗時不得留下部分資料。匯入前先產生 PWA safety backup。

| Android data | PWA store / action |
|---|---|
| `tables.work_records` snake_case | `workRecords` camelCase；保留 IDs、ISO date/time、minute values |
| `settings` | `settings`；原字串值與 effective date 保留 |
| annual/comp cycles | `leaveCycles` / `compLeaveCycles` |
| policy history | `compPolicies` |
| calendar overrides / official holidays | 對應同名 local stores |
| app metadata | `appMetadata`；另寫 PWA `schemaVersion: 1` |
| `manual_ledger_events` | 驗證後匯入 `ledger`，保留 IDs/reversal links |
| derived system ledger / monthly settlement snapshots | 不信任外部 balance；依 source data deterministic rebuild 後再產生 |
| legacy `monthly_settlements` | 暫存/轉換相容 store（實作前以 fixture 確認使用情境） |

PWA 自有 JSON/ZIP backup 將包含 `formatName`、`backupFormatVersion`、`databaseSchemaVersion`、`createdAt`、checksum 與 stores。Importer 支援 Android v1/v2 的欄位 default（如 calendar、comp cycles、policy history），未知新版本必須 fail closed。

## 5. PWA architecture / offline / future sync

- React pages → hooks/use-cases → repository contracts → Dexie adapters。Component 禁止直接操作 Dexie。
- Dexie schema 有獨立 database version，未來只做 forward migration。跨 stores 操作（record + rebuild ledger、restore）必須 transaction。
- `vite-plugin-pwa` 生成 manifest/service worker，precache app shell；部署 HTTPS 後可 standalone/install，已 cache 的 shell 可離線啟動。資料永遠 local-first。
- 政府假日是唯一規劃中的 online operation；離線需顯示明確提示。Browser CORS、metadata redirects、CSV encoding 與 cache 更新策略完成 spike 前維持 NOT STARTED。
- `src/sync/` 只留 boundary 文件，沒有 Supabase、auth 或 cloud SDK。未來 sync service 依 `RepositoryBundle`/DTO 與 local change journal 工作，不讓 UI 綁定供應商。
- SVG foundation icon 可供測試 manifest；正式發布前需產製/驗證 192、512、maskable 與 Apple touch bitmap icons。

## 6. Feature checklist

### DONE（0.1.0）

- [x] 獨立 React + TypeScript + Vite + Vitest 子專案
- [x] PWA manifest、generated service worker、app-shell precache configuration
- [x] Dexie v1 schema skeleton、domain models、repository contracts/local adapters
- [x] Mobile-first shell、清楚 selected/unselected bottom navigation、五頁 responsive skeleton
- [x] integer-minute formatting/conversion、month rollover、basic lunch overlap/overnight pure functions + tests
- [x] migration analysis、matrix、backup mapping、future sync boundary

### IN PROGRESS

- [ ] WorkRecord repository edge cases、transaction/use-case、React CRUD wiring
- [x] Typed settings、Phase 3 analysis 與 calendar service parity
- [ ] Production icon/splash/install UX 與跨瀏覽器 install QA

### NOT STARTED

- [ ] 完整 balance ledger rebuild、deduction priorities、conversion/reversal
- [ ] annual/comp cycles、monthly cap/transfer/cash/annual settlement
- [ ] official holiday **network** fetch/update（repository/cache/import、missing workday、special-date UI 已完成）
- [ ] yearly analysis and ledger balances（selected monthly analysis 已完成）
- [ ] Android import, PWA JSON backup/restore, safety backup
- [ ] five-sheet `.xlsx` export
- [ ] optional Supabase sync（明確不屬於首版）

## 7. Recommended delivery order

1. **Core parity**：把 Python tests 轉成 table-driven Vitest；補上 validation、cycle helper 與 exact cash rounding。
2. **WorkRecord CRUD**：Dexie transaction、同日 upsert、edit/cancel/delete、recent/month list；每次 mutation 導向 ledger rebuild use-case。
3. **Settings/calendar**：typed settings、tracking start、special overrides；使用 packaged holiday JSON，另做官方資料 CORS spike。
4. **Ledger/leave**：append-only models、priority、manual conversion/reversal、cycle grant/settlement、monthly/annual comp buckets/cash。
5. **Calendar/analysis**：selected calendar month/year、missing days、full metric and balance parity。
6. **Portability**：Android backup fixtures → validated importer；PWA backup/restore；五 sheet Excel。
7. **PWA polish**：offline/update prompts、icons/splash、360/390/411/768/desktop 與 Android Chrome/iOS Safari QA。
8. **Optional sync**：需求確認後才增加 local change journal + Supabase adapter；不得改寫 domain/UI。

## 8. Foundation acceptance notes

`npm run dev` 提供 Vite development server；service worker 的完整離線行為應以 production `npm run build && npm run preview` 驗證。Skeleton 中尚未可用的 action 明確 disabled 或標示「尚未實作」，不製造假資料、不宣稱 DONE。
