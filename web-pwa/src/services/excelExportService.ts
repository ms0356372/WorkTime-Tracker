import type {WorkTimeDatabase} from '../db/database'
import {db} from '../db/database'
import type {ExcelExportScope,ExcelSnapshot} from './excelReportBuilder'
import {buildExcelReport} from './excelReportBuilder'
import {writeXlsx} from './xlsxWriter'
import {localISODate} from './calendarService'

export const XLSX_MIME='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
export interface ExcelArtifact{filename:string;mime:string;bytes:Uint8Array;blob:Blob}

export class ExcelExportService{
  constructor(private database:WorkTimeDatabase=db){}
  async snapshot():Promise<ExcelSnapshot>{
    return this.database.transaction('r',[this.database.workRecords,this.database.settings,this.database.ledger,this.database.calendarOverrides,this.database.officialHolidays,this.database.compMonthlySettlements],async()=>{
      const [records,settingRows,ledger,overrides,holidays,settlements]=await Promise.all([this.database.workRecords.orderBy('workDate').toArray(),this.database.settings.toArray(),this.database.ledger.orderBy('transactionDatetime').toArray(),this.database.calendarOverrides.orderBy('workDate').toArray(),this.database.officialHolidays.toArray(),this.database.compMonthlySettlements.toArray()])
      return {records,settings:Object.fromEntries(settingRows.map(row=>[row.key,row.value])),ledger,overrides,holidays,settlements}
    })
  }
  async create(scope:ExcelExportScope,today=localISODate()):Promise<ExcelArtifact>{const report=buildExcelReport(await this.snapshot(),scope,today),bytes=writeXlsx(report.sheets),blob=new Blob([bytes.buffer as ArrayBuffer],{type:XLSX_MIME});return {filename:report.filename,mime:XLSX_MIME,bytes,blob}}
}
