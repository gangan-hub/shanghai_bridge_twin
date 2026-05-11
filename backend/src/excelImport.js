import pg from "pg";
import dotenv from "dotenv";
import path from "path";
import { execSync } from 'child_process';
import { query } from "./db.js";

// 坐标转换函数 (GCJ-02 to WGS-84)
function gcj02_to_wgs84(lng, lat) {
    const PI = 3.1415926535897932384626;
    const A = 6378245.0;
    const EE = 0.00669342162296594323;

    function transformLat(x, y) {
        let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
        ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(y * PI) + 40.0 * Math.sin(y / 3.0 * PI)) * 2.0 / 3.0;
        ret += (160.0 * Math.sin(y / 12.0 * PI) + 320 * Math.sin(y * PI / 30.0)) * 2.0 / 3.0;
        return ret;
    }

    function transformLon(x, y) {
        let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
        ret += (20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0 / 3.0;
        ret += (20.0 * Math.sin(x * PI) + 40.0 * Math.sin(x / 3.0 * Math.PI)) * 2.0 / 3.0;
        ret += (150.0 * Math.sin(x / 12.0 * PI) + 300.0 * Math.sin(x / 30.0 * PI)) * 2.0 / 3.0;
        return ret;
    }

    let dlat = transformLat(lng - 105.0, lat - 35.0);
    let dlng = transformLon(lng - 105.0, lat - 35.0);
    let radlat = lat / 180.0 * PI;
    let magic = Math.sin(radlat);
    magic = 1 - EE * magic * magic;
    let sqrtmagic = Math.sqrt(magic);
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI);
    dlng = (dlng * 180.0) / (A / sqrtmagic * Math.cos(radlat) * PI);
    let mglat = lat + dlat;
    let mglng = lng + dlng;
    return [lng * 2 - mglng, lat * 2 - mglat];
}

export async function importExcelData() {
  const excelPath = path.resolve(process.cwd(), "..", "ai_models", "data", "上海市桥梁POI数据.xlsx");
  console.log(`[ExcelImport] Loading data from: ${excelPath}`);

  try {
    // 使用 python 脚本读取 excel 并转换为 JSON
    const cmd = `python -c "import pandas as pd, json, sys; df = pd.read_excel(r'${excelPath}'); print(df.to_json(orient='records'))"`;
    const jsonStr = execSync(cmd, { encoding: 'utf8' });
    const data = JSON.parse(jsonStr);

    console.log(`[ExcelImport] Found ${data.length} records. Truncating bridges table...`);
    await query("TRUNCATE TABLE bridges");

    for (let i = 0; i < data.length; i++) {
      const row = data[i];
      const name = row.name;
      const lng = parseFloat(row.x);
      const lat = parseFloat(row.y);
      
      const wgs = gcj02_to_wgs84(lng, lat);
      const code = `BRIDGE_${i.toString().padStart(3, '0')}`;

      await query(
        "INSERT INTO bridges (code, name, lon, lat, wgs_lon, wgs_lat, bridge_type) VALUES ($1, $2, $3, $4, $5, $6, $7)",
        [code, name, lng, lat, wgs[0], wgs[1], '桥梁']
      );
    }
    console.log("[ExcelImport] Data import successful.");
    return { success: true, count: data.length };
  } catch (error) {
    console.error("[ExcelImport] Failed to import Excel data:", error.message);
    throw error;
  }
}
