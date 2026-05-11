import sys, json
import pandas as pd

path = sys.argv[1]
df = pd.read_excel(path)
col = "bridge_type" if "bridge_type" in df.columns else "桥隧类型"
if col not in df.columns:
    df["bridge_type"] = df["typecode"].astype(str).str[0:2].map(
        {"19": "立交桥", "20": "梁桥", "21": "拱桥", "22": "隧道"}
    )
    col = "bridge_type"
df[col] = df[col].fillna("未知")
print(df.to_json(orient="records", force_ascii=False))
