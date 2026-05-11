import { execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const PYTHON_EXE = "C:\\Program Files\\Python312\\python.exe";
const tmpFile = path.join(process.env.TEMP || ".", `_excel_cols_${Date.now()}.json`);

const pyCode = `
import json, sys
import pandas as pd
xl = pd.ExcelFile(sys.argv[1])
df = xl.parse(xl.sheet_names[0])
result = {"columns": list(df.columns), "first_3_rows": df.head(3).to_dict(orient="records"), "shape": list(df.shape)}
with open(sys.argv[2], "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, default=str)
`;

const tmpPy = path.join(process.env.TEMP || ".", "_tmp_read_cols.py");
fs.writeFileSync(tmpPy, pyCode);

const xlsx = path.resolve("f:\\Trae code\\002\\ai_models_flow\\shanghai_data\\shanghaidata_x.xlsx");
execFile(PYTHON_EXE, [tmpPy, xlsx, tmpFile], { maxBuffer: 32*1024*1024 }, (err) => {
  if (err) { console.error("Error:", err.message); process.exit(1); }
  const data = JSON.parse(fs.readFileSync(tmpFile, "utf-8"));
  console.log("=== Excel 列名 ===");
  data.columns.forEach((c, i) => console.log(`  ${i}: "${c}"`));
  console.log("\n=== 前3行数据 ===");
  console.log(JSON.stringify(data.first_3_rows, null, 2));
  console.log("\n=== 数据维度 ===", data.shape);
  fs.unlinkSync(tmpFile);
  fs.unlinkSync(tmpPy);
  process.exit(0);
});
