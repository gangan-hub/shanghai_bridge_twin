import { query } from "./db.js";

let cached = null;

export function clearCapabilitiesCache() {
  cached = null;
}

export async function getDbCapabilities() {
  if (cached) return cached;

  cached = (async () => {
    const ext = await query("SELECT 1 FROM pg_extension WHERE extname = 'postgis' LIMIT 1");
    const hasPostgis = ext.rowCount > 0;

    // 仅在有 PostGIS 时才检查字段存在性（避免无 PostGIS 时触发类型/函数相关依赖）
    let hasLocationColumn = false;
    if (hasPostgis) {
      const col = await query(
        `
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'bridges' AND column_name = 'location'
        LIMIT 1
        `
      );
      hasLocationColumn = col.rowCount > 0;
    }

    return { hasPostgis, hasLocationColumn, mode: hasPostgis && hasLocationColumn ? "postgis" : "nopostgis" };
  })();

  return cached;
}

