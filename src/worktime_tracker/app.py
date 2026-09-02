"""BeeWare Toga mobile application composition root."""
from pathlib import Path
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
from worktime_tracker.config import APP_NAME
from worktime_tracker.database import Database, LedgerRepository, SettingsRepository, WorkRecordRepository
from worktime_tracker.views.dashboard_view import DashboardView
from worktime_tracker.views.settings_view import SettingsView
class WorkTimeApp(toga.App):
    def startup(self):
        data_dir=Path(self.paths.data); data_dir.mkdir(parents=True,exist_ok=True)
        self.db=Database(data_dir/"worktime.sqlite3"); self.repository=WorkRecordRepository(self.db)
        self.settings_repository=SettingsRepository(self.db); self.ledger_repository=LedgerRepository(self.db)
        tabs=toga.OptionContainer(style=Pack(flex=1))
        tabs.content=[("首頁",DashboardView(self.repository).build()),("紀錄",self._records()),("日曆",toga.Box(children=[toga.Label("月曆（紀錄依日期排列）")],style=Pack(direction=COLUMN,padding=16))),("分析",toga.Box(children=[toga.Label("分析資料將依本機紀錄即時計算")],style=Pack(direction=COLUMN,padding=16))),("設定",SettingsView(self.settings_repository,self.ledger_repository).build())]
        self.main_window=toga.MainWindow(title=APP_NAME); self.main_window.content=tabs; self.main_window.show()
    def _records(self):
        self.date=toga.DateInput(); self.start=toga.TimeInput(); self.end=toga.TimeInput(); self.note=toga.TextInput(placeholder="備註")
        save=toga.Button("儲存紀錄",on_press=self.save_record)
        return toga.Box(children=[toga.Label("新增每日紀錄"),self.date,toga.Box(children=[self.start,self.end],style=Pack(direction=ROW)),self.note,save],style=Pack(direction=COLUMN,padding=16,gap=8))
    async def save_record(self,widget):
        from worktime_tracker.models import WorkRecord
        try:
            record=WorkRecord(self.date.value,self.start.value.strftime("%H:%M"),self.end.value.strftime("%H:%M"),note=self.note.value)
            self.repository.save(record); await self.main_window.dialog(toga.InfoDialog("完成","紀錄已儲存。"))
        except Exception:
            await self.main_window.dialog(toga.ErrorDialog("無法儲存","請檢查日期與時間後再試一次。"))
def main(): return WorkTimeApp()
