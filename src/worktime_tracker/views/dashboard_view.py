"""Dashboard card view."""
import toga
from toga.style import Pack
from toga.style.pack import COLUMN
class DashboardView:
    def __init__(self,repository): self.repository=repository
    def build(self):
        labels=["今天工時：尚無紀錄","本月工時：依紀錄計算","目前補休：0 小時","剩餘特休：尚未設定","疲累指數：0 / 100（低）","此指數僅依工作時數、連續工作與休息時間估算工作負荷，不代表醫療診斷。"]
        return toga.Box(children=[toga.Label(x,style=Pack(padding=10)) for x in labels],style=Pack(direction=COLUMN,padding=12))
