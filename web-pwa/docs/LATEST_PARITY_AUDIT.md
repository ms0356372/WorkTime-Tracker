# Latest Android → PWA Version Parity Audit and Reconciliation

Audit date: 2026-09-04. Source priority: current Python source, current Python tests, supplied current-app screenshots, PWA, then old migration notes. Android/Python was read-only. No screenshot image was present in the task payload or repository, so screenshot-only claims cannot be verified; they are called out rather than inferred.

## Source / screenshot mismatch

**SCREENSHOT INPUT UNAVAILABLE.** No uploaded image could be enumerated or inspected. Consequently there is no observed source/screenshot contradiction, but every screenshot-only field or visual state remains **UNVERIFIED**, not silently accepted from old documentation. A follow-up audit must attach the images to close this evidence gap.

## Latest Android feature inventory

The source implements daily record CRUD/edit mode; overlap-only lunch deduction and explicit overnight validation; calendar override > official holiday > weekday priority; calculation-start-aware missing workdays; monthly and selected-year analysis; deterministic ledger rebuild; comp/annual deduction priority; annual leave and comp cycles; monthly/annual comp settlement modes, caps and integer-cent cash-out; conversion and append-only reversal; five-sheet Excel export; and validated full backup/restore. Settings exposes all policies, calendar maintenance, conversion/history, and portability operations.

## Five-page parity matrix

| Page / capability | Status | Evidence and disposition |
|---|---|---|
| HOME today work | MISSING | Android has today work; PWA still shows month-oriented cards only. Roadmap Phase 4. |
| HOME month work | MATCH | Repository-backed selected current month calculation. |
| HOME available/monthly/annual comp and annual leave | INTENTIONALLY DEFERRED | Requires ledger/cycle engine, never claimed functional in Phase 3. |
| HOME export scope / Excel | INTENTIONALLY DEFERRED | Export belongs to portability phase. |
| RECORDS date, clock-in/out, note, save | MATCH | Persisted through repository with configured lunch/standard minutes. |
| RECORDS edit state, locked date, save edit, cancel | MATCH | Reconciled in this audit. |
| RECORDS today work | MATCH | Now reads today's persisted record, rather than the last save preview. |
| RECORDS recent date/times/work, modify/delete | MATCH | Five recent records, matching Android count and actions. Delete does not yet rebuild ledger because ledger is deferred. |
| CALENDAR month navigation and month record list | MATCH | Reconciled from a full calendar-day listing to Android's month-record cards. |
| CALENDAR date/work/Edit/Delete/empty message | MATCH | Reconciled in this audit. |
| CALENDAR special dates, official holiday and workday labels | PARTIAL | Calendar business rules are used by analysis, but Android month-record UI itself lists records only; settings supplies labels. Browser official network sync remains unavailable. |
| ANALYSIS selected month; total, attendance, average, overtime, shortfall, holiday work | MATCH | Calendar-aware monthly summary. |
| ANALYSIS scheduled/missing workdays | MATCH | Extra diagnostics preserve latest safe-cache rule. |
| ANALYSIS selected-year total and attendance | MATCH | Reconciled in this audit; selected year is used. |
| ANALYSIS comp total/month/year, annual leave | INTENTIONALLY DEFERRED | Depends on deferred ledger. |
| SETTINGS standard work time, lunch, calculation start | MATCH | Integer minutes and validated lunch interval. |
| SETTINGS work calendar Mon–Fri | MATCH | Weekday fallback is implemented in calendar service. |
| SETTINGS special non-workday/company make-up day/company holiday/delete | PARTIAL | WORKDAY/NON_WORKDAY override and delete exist; labels remain technical and company-holiday distinctions are represented by note rather than separate choices. |
| SETTINGS Taiwan official holidays/update/status | PARTIAL | Local annual JSON replacement exists; current Android packaged/network DGPA synchronization and status are not parity. |
| SETTINGS deduction priority; annual entitlement/date/cycle/summary | INTENTIONALLY DEFERRED | Ledger/leave phase. |
| SETTINGS comp mode/date/cap/rate/history/year/balance split | INTENTIONALLY DEFERRED | Settlement phase. |
| SETTINGS conversion source/target/hours/minutes/note/reversal | INTENTIONALLY DEFERRED | Ledger phase. |
| SETTINGS full Backup/Restore | INTENTIONALLY DEFERRED | Portability phase. |

## Business-logic parity

| Rule | Status | Finding |
|---|---|---|
| WorkRecord calculation / integer minutes | MATCH | No floating duration. |
| Lunch overlap | MATCH | Only actual interval overlap is deducted. Inverted lunch is now rejected like Python rather than treated as an overnight break. |
| Overnight | MATCH | Earlier clock-out requires explicit `overnight`; current Android form creates non-overnight records. |
| Standard work minutes | MATCH | Global value feeds calendar analysis and is snapshotted on records. |
| Workday priority / official holiday / special override | MATCH | Override > holiday > weekday/weekend. |
| Calculation start / missing workdays | MATCH | Excludes earlier days, today/future; weekday missing requires reliable holiday cache unless explicitly overridden. |
| Monthly analysis | MATCH | Selected month, calendar standard, missing shortfall and holiday work. |
| Annual analysis | PARTIAL | Work and attendance now match; leave metrics await ledger. |
| Comp leave / annual leave / ledger / settlements / cash-out / conversion / reversal | INTENTIONALLY DEFERRED | Models/stores are foundation only; no functional claim is made. |
| Backup / Excel | INTENTIONALLY DEFERRED | Mappings exist, implementation does not. |

## Outdated / regression findings

Five uses of older behavior were found:

1. **OUTDATED IMPLEMENTATION — lunch:** PWA interpreted an inverted lunch interval as overnight; latest Python rejects it. **Fixed.**
2. **OUTDATED IMPLEMENTATION — record editing:** Phase 2/3 claimed CRUD while UI lacked Android edit/load/cancel mode. **Fixed.**
3. **OUTDATED IMPLEMENTATION — today work:** PWA displayed only the last saved preview as “this entry,” not persisted today work. **Fixed.**
4. **OUTDATED IMPLEMENTATION — month records:** PWA rendered every calendar date and omitted Android record-card edit/delete/empty behavior. **Fixed.**
5. **OUTDATED IMPLEMENTATION — annual analysis:** latest Android shows selected-year total/attendance while PWA omitted both despite claiming Analysis migrated. **Fixed.**

No deferred ledger, leave, export, or backup item was reclassified as a regression: those were never functionally completed. The old migration document's broad `IMPLEMENTED` labels must be read as historical Phase 3 claims; this audit is authoritative.

## Updated migration roadmap

- **Phase 4 — parity closure for visible foundations:** today-work Home card; user-facing special-date categories; packaged Taiwan holiday data and browser-safe update/status; delete confirmation and calendar/record mutation use-case boundaries; accessibility and screenshot QA.
- **Phase 5 — ledger and leave core:** deterministic replay, missing-day events, deduction priority, annual leave cycles/grants/settlement, balances, selected-year leave metrics, complete Home/Analysis/Settings balance information.
- **Phase 6 — comp settlement:** annual/monthly policies, effective history, monthly/annual buckets, cap transfer, exact integer-cent cash-out, settlement history and all current-cycle summaries.
- **Phase 7 — conversion and audit:** comp ↔ annual conversion, validation, manual ledger history, append-only reversal and UI.
- **Phase 8 — portability:** Android backup v1/v2 import, PWA full backup/safety backup/restore, checksum/schema validation and deterministic derived-data rebuild.
- **Phase 9 — Excel:** all/leave-year scope and Android-equivalent five-sheet workbook with calendar-aware summaries.
- **Phase 10 — release parity QA:** supplied Android screenshot comparison at supported breakpoints, offline/update/install flows, production icons, cross-browser/device checks. Optional cloud sync remains outside Android parity and requires separate approval.

## Verification and scope

`verify_pwa.bat` still checks Node/npm, dependencies, tests, production build, and `dist/index.html`; it was not modified. Phase 4 verification completed with 43 passing Vitest tests, a zero-error TypeScript/Vite production build, generated manifest/service worker/assets, and a responding production preview. The final Git scope audit contains only `web-pwa/**`; Android/Python files were not modified.

## Phase 4 closure (2026-09-07)

Phase 4 closes the visible-foundation gaps: Home now obtains today's record by its local ISO date directly from IndexedDB and separately calculates the current-month summary. Work-record saves and confirmed deletes pass through one mutation use-case and emit one refresh event; Records and Calendar share its confirmation-aware deletion path. Leave and ledger values remain **INTENTIONALLY DEFERRED** and no zero balance is presented.

Special-date presentation now offers **公司補班日**, **公司假日**, and **特殊非工作日**, mapped respectively to `WORKDAY`, `NON_WORKDAY`, and `NON_WORKDAY`. Dexie schema v2 adds the display category and migrates legacy rows conservatively (`WORKDAY` → company makeup day; `NON_WORKDAY` → special non-workday). The business priority remains special override > official holiday > weekday.

Packaged DGPA-derived 2026 and 2027 JSON is precached by the PWA, validated atomically, and loaded into IndexedDB on first annual use. Settings reports each relevant year's loaded status and last successful update. A failed package update leaves the previous annual cache untouched. Advanced validated JSON import remains available. Calendar/analysis reuse cached data rather than fetching on every calculation.

Delete confirmations include the record date. User-readable load/save/delete failures, visible focus outlines, semantic form labels/status messages, 44 px controls, wrapping record actions, narrow-screen one-column forms/status, non-compressing month navigation, and existing bottom safe-area padding establish the Phase 4 accessibility/responsive baseline.

**SOURCE MISMATCH:** current Python Settings exposes the technical two-way choice “上班日 / 非上班日”, while this Phase explicitly requires three user-facing categories. The PWA therefore keeps the Python `WORKDAY` / `NON_WORKDAY` core and adds only non-destructive presentation metadata as required by this Phase.

**SCREENSHOT QA NOT AVAILABLE:** no current Android screenshot was supplied in this task payload or found in the repository. Automated production preview was checked, but Android visual comparison cannot honestly be claimed.


## Phase 5 reconciliation (2026-09-07)

**DONE / MATCH:** deterministic persisted Ledger core; SYSTEM/MANUAL replay; WorkRecord and missing-workday earning/deduction; both deduction priorities including Python's negative-last-priority legacy deficit; annual entitlement, settlement date, cycle persistence, leap-day clamp, activation-safe grant/settlement; and real current comp/annual balances on Home, Analysis, and Settings. Core arithmetic remains integer minutes.

There is no source/test mismatch for uncovered deficits: current `LeaveBalanceService.deduct_leave()` and its tests require charging the remaining deficit to the last-priority leave type, which can become negative. Calendar classification is shared (special override > official holiday > weekday), and today/future are excluded from automatic missing-day events.

**INTENTIONALLY DEFERRED (Phase 6):** monthly versus annual comp mode, buckets, cap, transfer, cash-out/rate, settlement policy/history, and annual comp settlement. **INTENTIONALLY DEFERRED (Phase 7+):** conversion/reversal UI and audit history, backup/restore, Excel, Supabase/cloud sync. Dexie remains at schema v2 because all Phase 5 stores and indexes were already safely present.

## Phase 6 reconciliation (2026-09-07)

**DONE / MATCH:** ANNUAL/MONTHLY compensation-leave policy; settlement-date-derived current comp cycle; effective-from-cycle-start policy history; monthly/annual buckets; monthly-first bucket deduction with legacy negative annual-comp deficit; completed-month-only transfer; integer-minute cap; explicit excess cash event with Python-compatible integer-cent rounding; derived monthly settlement history; activation-safe annual comp settlement; and shared Home, Analysis, and Settings summaries.

Replay generates month transfer at 23:58:00, cash settlement at 23:58:30, and annual settlement at 23:59:59. Ledger and monthly settlement replacement share one Dexie transaction, while manual rows and WorkRecords remain untouched. Existing schema v2 already contained all stores and indexes, so Phase 6 requires no database version increase or destructive migration.

**INTENTIONALLY DEFERRED (Phase 7):** Comp ↔ Annual conversion, conversion form/history, and reversal. **INTENTIONALLY DEFERRED (Phase 8+):** Backup/Restore and Android import, Excel export, Supabase, and cloud sync.
