# aqee/extractors/xlsx.py
from typing import Dict, Any
import pandas as pd

def extract_xlsx(path: str, sheet: int | str | None = None) -> Dict[str, Any]:
    xl = pd.ExcelFile(path)
    sheet_name = sheet if sheet is not None else xl.sheet_names[0]
    df = xl.parse(sheet_name)
    headers = list(df.columns)
    rows = df.astype(str).fillna("").values.tolist()
    return {
        "text_blocks": [],
        "table_blocks": [{"headers": headers, "rows": rows}],
        "header_candidates": headers
    }
