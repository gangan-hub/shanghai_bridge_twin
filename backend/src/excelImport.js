import { execFile } from "node:child_process";
import path from "node:path";
import fs from "node:fs";
import os from "node:os";
import { query } from "./db.js";

const PYTHON_EXE = "C:\\Program Files\\Python312\\python.exe";
const PROJECT_ROOT = path.resolve(import.meta.dirname, "..", "..");
const SHANGHAI_XLSX = path.join(
  PROJECT_ROOT,
  "ai_models_flow",
  "shanghai_data",
  "shanghaidata_x.xlsx",
);

const PY_SCRIPT = path.join(import.meta.dirname, "_read_excel.py");

function runPython() {
  return new Promise((resolve, reject) => {
    // Write to a temp file to avoid Windows stdout encoding issues (GBK vs UTF-8)
    const tmpFile = path.join(os.tmpdir(), `_excel_import_${Date.now()}.json`);
    execFile(PYTHON_EXE, [PY_SCRIPT, SHANGHAI_XLSX, tmpFile], {
      maxBuffer: 32 * 1024 * 1024,
    }, (err) => {
      if (err) {
        try { fs.unlinkSync(tmpFile); } catch {}
        return reject(err);
      }
      try {
        const raw = fs.readFileSync(tmpFile, "utf-8");
        fs.unlinkSync(tmpFile);
        const data = JSON.parse(raw);
        if (data && data.error) return reject(new Error(data.error));
        resolve(data);
      } catch (e) {
        try { fs.unlinkSync(tmpFile); } catch {}
        return reject(e);
      }
    });
  });
}

export async function importExcelData() {
  const rows = await runPython();
  if (!Array.isArray(rows) || rows.length === 0) {
    throw new Error("No data read from Excel");
  }

  // Ensure all required columns exist
  await query(`ALTER TABLE bridges ADD COLUMN IF NOT EXISTS typecode VARCHAR(20)`);
  await query(`ALTER TABLE bridges ADD COLUMN IF NOT EXISTS node_0base INTEGER`);
  await query(`ALTER TABLE bridges ADD COLUMN IF NOT EXISTS display_idx INTEGER`);

  // Drop NOT NULL constraints on coordinate columns so we can insert without coordinates
  await query(`ALTER TABLE bridges ALTER COLUMN lon DROP NOT NULL`);
  await query(`ALTER TABLE bridges ALTER COLUMN lat DROP NOT NULL`);

  // Clear all existing data — Excel is the single source of truth
  await query(`TRUNCATE TABLE bridges RESTART IDENTITY`);

  let count = 0;
  // typecode → 桥隧类型 mapping
  const typecodeMap = {};

  for (const r of rows) {
    const node0 = Number(r[0]);
    const typecode = String(r[1]).trim();
    const name = String(r[2] ?? "").trim();
    const bridgeType = String(r[3] ?? "").trim();
    const idx = node0 + 1; // node starts from 0 → store from 1

    await query(
      `INSERT INTO bridges (code, name, bridge_type, typecode, node_0base, display_idx, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6, NOW())`,
      [String(idx), name, bridgeType, typecode, node0, idx],
    );

    if (typecode && bridgeType) {
      typecodeMap[typecode] = bridgeType;
    }
    count++;
  }

  return { count, typecodeMap };
}

/**
 * Returns the typecode ↔ 桥隧类型 mapping (static, built from known data).
 */
export async function getTypecodeMapping() {
  const { rows } = await query(
    `SELECT DISTINCT typecode, bridge_type FROM bridges WHERE typecode IS NOT NULL AND bridge_type IS NOT NULL ORDER BY typecode`,
  );
  const map = {};
  for (const r of rows) {
    map[r.typecode] = r.bridge_type;
  }
  return map;
}
