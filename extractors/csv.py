# aqee/extractors/csv.py
from typing import Dict, Any
import pandas as pd

def extract_csv(path: str) -> Dict[str, Any]:
    df = pd.read_csv(path)
    headers = list(df.columns)
    rows = df.astype(str).fillna("").values.tolist()
    return {
        "text_blocks": [],
        "table_blocks": [{"headers": headers, "rows": rows}],
        "header_candidates": headers
    }
