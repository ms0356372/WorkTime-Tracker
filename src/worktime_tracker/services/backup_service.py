"""Portable JSON backup and atomic restore."""
import json
from datetime import datetime, timezone
from pathlib import Path
TABLES=("work_records","settings","leave_cycles","balance_ledger","monthly_settlements","app_metadata")
def create_backup(db,path):
    data={"format_version":1,"created_at":datetime.now(timezone.utc).isoformat(),"tables":{t:[dict(r) for r in db.connection.execute(f"SELECT * FROM {t}")] for t in TABLES}}
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
def restore_backup(db,path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format_version")!=1: raise ValueError("不支援的備份格式。")
    with db.transaction() as con:
        for table in reversed(TABLES): con.execute(f"DELETE FROM {table}")
        for table in TABLES:
            for row in data["tables"].get(table,[]):
                columns=",".join(row); marks=",".join("?" for _ in row)
                con.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})",tuple(row.values()))
