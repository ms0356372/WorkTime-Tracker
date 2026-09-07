export interface BackupManifest {format_name:string;backup_format_version:number;app_version:string;created_at:string;database_schema_version:number;record_count:number;data_sha256:string}
export interface AndroidWorkRecordRow{id:number;work_date:string;clock_in:string|null;clock_out:string|null;break_start:string|null;break_end:string|null;deduct_break:boolean|0|1;standard_minutes:number;note:string;workday_type:string;overnight:boolean|0|1}
export interface AndroidSettingRow{key:string;value:string;effective_date?:string|null}
export interface AndroidLeaveCycleRow{id:number;start_date:string;end_date:string;total_minutes:number}
export interface AndroidCompCycleRow{id:number;start_date:string;end_date:string}
export interface AndroidCompPolicyRow{id:number;effective_from:string;mode:'ANNUAL'|'MONTHLY';monthly_cap_minutes:number;cash_hourly_rate_cents:number;created_at:string}
export interface AndroidMonthlySettlementRow{id:number;year:number;month:number;minutes:number;rule:string}
export interface AndroidCalendarOverrideRow{id:number;work_date:string;day_type:'WORKDAY'|'NON_WORKDAY';note?:string|null;created_at?:string|null;updated_at?:string|null}
export interface AndroidOfficialHolidayRow{holiday_date:string;name:string;year:number;source:string;synced_at:string}
export interface AndroidAppMetadataRow{key:string;value:string}
export interface AndroidManualLedgerRow{id:number;entry_date:string;entry_type:string;reason:string;comp_change?:number;annual_change?:number;comp_balance?:number;annual_balance?:number;source_record_id?:number|null;transaction_datetime:string;transaction_type:string;ledger_origin:'MANUAL';source_leave_type?:string|null;target_leave_type?:string|null;source_minutes?:number|null;target_minutes?:number|null;note?:string|null;created_at:string;reversal_of_id?:number|null;monthly_comp_balance?:number;annual_comp_balance?:number;cash_amount_cents?:number;cash_hourly_rate_cents?:number}
export interface PwaDailyCapPolicy{enabled:boolean;daily_cap_minutes:number}
export interface PwaExtensions{calendar_override_categories?:Record<string,string>;comp_daily_cap_policies?:Record<string,PwaDailyCapPolicy>;producer?:'PWA'}
export interface BackupTables{work_records:AndroidWorkRecordRow[];settings:AndroidSettingRow[];leave_cycles:AndroidLeaveCycleRow[];comp_leave_cycles:AndroidCompCycleRow[];comp_settlement_policy_history:AndroidCompPolicyRow[];monthly_settlements:AndroidMonthlySettlementRow[];app_metadata:AndroidAppMetadataRow[];calendar_overrides:AndroidCalendarOverrideRow[];official_holidays:AndroidOfficialHolidayRow[]}
export interface BackupData{tables:BackupTables;manual_ledger_events:AndroidManualLedgerRow[];pwa_extensions?:PwaExtensions}
