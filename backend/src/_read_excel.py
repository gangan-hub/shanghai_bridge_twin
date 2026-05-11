import json, sys

try:
    import pandas as pd
except ImportError:
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump({"error": "pandas not installed"}, f)
    sys.exit(0)

try:
    xl = pd.ExcelFile(sys.argv[1])
    df = xl.parse(xl.sheet_names[0])
    wanted = ["node", "typecode", "name", "\u6865\u96a7\u7c7b\u578b"]
    for c in wanted:
        if c not in df.columns:
            with open(sys.argv[2], "w", encoding="utf-8") as f:
                json.dump({"error": f"missing column: {c}"}, f, ensure_ascii=False)
            sys.exit(0)
    df = df[wanted].dropna(subset=["node"])
    df["node"] = df["node"].astype(int)
    df["typecode"] = df["typecode"].astype(int)
    df["name"] = df["name"].fillna("").astype(str)
    df["\u6865\u96a7\u7c7b\u578b"] = df["\u6865\u96a7\u7c7b\u578b"].fillna("").astype(str)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(df.values.tolist(), f, ensure_ascii=False)
except Exception as e:
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump({"error": str(e)}, f, ensure_ascii=False)
