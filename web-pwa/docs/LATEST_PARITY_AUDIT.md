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

`verify_pwa.bat` still checks Node/npm, dependencies, tests, production build, and `dist/index.html`; it was not modified. Required npm verification was attempted, but dependencies were absent and registry access returned HTTP 403, so test/build execution is environment-blocked. The final Git scope audit must contain only `web-pwa/**`. Android/Python files were not modified.
