"""Tiny standard-library XLSX writer fallback for restricted/offline environments."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

@dataclass
class Worksheet:
    name: str
    rows: dict[int, dict[int, object]] = field(default_factory=dict)
    freeze: bool = False
    filter_range: tuple[int,int,int,int] | None = None
    widths: tuple[int,int,float] | None = None
    def freeze_panes(self,row,col): self.freeze=True
    def autofilter(self,*values): self.filter_range=values
    def set_column(self,start,end,width): self.widths=(start,end,width)
    def set_row(self,*args): pass
    def write_row(self,row,col,values,cell_format=None):
        for offset,value in enumerate(values): self.rows.setdefault(row,{})[col+offset]=value

class Workbook:
    """Subset of XlsxWriter used by this project; produces valid OOXML."""
    def __init__(self,path): self.path=Path(path); self.sheets=[]
    def add_format(self,options): return options
    def add_worksheet(self,name):
        sheet=Worksheet(name); self.sheets.append(sheet); return sheet
    def close(self):
        with ZipFile(self.path,"w",ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml",self._content_types())
            archive.writestr("_rels/.rels",'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
            archive.writestr("xl/workbook.xml",self._workbook())
            archive.writestr("xl/_rels/workbook.xml.rels",self._workbook_rels())
            archive.writestr("xl/styles.xml",'<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font/><font><b/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>')
            for index,sheet in enumerate(self.sheets,1): archive.writestr(f"xl/worksheets/sheet{index}.xml",self._sheet(sheet))
    def _content_types(self):
        sheets="".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(self.sheets)+1))
        return f'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>{sheets}</Types>'
    def _workbook(self):
        sheets="".join(f'<sheet name="{escape(s.name)}" sheetId="{i}" r:id="rId{i}"/>' for i,s in enumerate(self.sheets,1))
        return f'<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{sheets}</sheets></workbook>'
    def _workbook_rels(self):
        rels="".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(self.sheets)+1))
        return f'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}<Relationship Id="rId{len(self.sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    def _sheet(self,sheet):
        rows=[]
        for row,cells in sorted(sheet.rows.items()):
            values=[]
            for col,value in sorted(cells.items()):
                ref=f"{self._column(col)}{row+1}"; style=' s="1"' if row==0 else ""
                if isinstance(value,(int,float)): cell=f'<c r="{ref}"{style}><v>{value}</v></c>'
                elif value is None: cell=f'<c r="{ref}"{style}/>'
                else: cell=f'<c r="{ref}" t="inlineStr"{style}><is><t>{escape(str(value))}</t></is></c>'
                values.append(cell)
            rows.append(f'<row r="{row+1}">{"".join(values)}</row>')
        pane='<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews>' if sheet.freeze else ""
        filt=""
        if sheet.filter_range:
            r1,c1,r2,c2=sheet.filter_range; filt=f'<autoFilter ref="{self._column(c1)}{r1+1}:{self._column(c2)}{r2+1}"/>'
        cols=f'<cols><col min="{sheet.widths[0]+1}" max="{sheet.widths[1]+1}" width="{sheet.widths[2]}" customWidth="1"/></cols>' if sheet.widths else ""
        return f'<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{pane}{cols}<sheetData>{"".join(rows)}</sheetData>{filt}</worksheet>'
    @staticmethod
    def _column(index):
        result=""; index+=1
        while index: index,remainder=divmod(index-1,26); result=chr(65+remainder)+result
        return result
