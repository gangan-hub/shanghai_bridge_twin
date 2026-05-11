import { query } from "./db.js";
import { clearCapabilitiesCache } from "./capabilities.js";

/**
 * 启动时自动执行：补齐列、若桥梁表为空则补种示例数据（3 座桥）。
 * 避免未跑 db:init 时 SELECT 引用不存在的列导致列表 500。
 */
export async function runMigrations() {
  try {
    const exists = await query(
      `SELECT EXISTS (
      SELECT 1 FROM information_schema.tables
      WHERE table_schema = 'public' AND table_name = 'bridges'
    ) AS e`
    );
    if (!exists.rows[0]?.e) {
      console.warn("migrate: table public.bridges 不存在，请先执行 npm run db:init");
      return;
    }

    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS wgs_lon NUMERIC(9,6)");
    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS wgs_lat NUMERIC(9,6)");

    // 补齐 /bridges 查询与 reload_from_xlsx 所需的全部列，避免缺列导致列表 500
    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS bd_lon NUMERIC(9,6)");
    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS bd_lat NUMERIC(9,6)");
    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS node_0base INTEGER");
    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS display_idx INTEGER");
    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS func_name VARCHAR(100)");
    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS road_name VARCHAR(200)");
    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS road_class VARCHAR(50)");
    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS lanes VARCHAR(50)");
    await query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS poi_flow VARCHAR(50)");

    const colRows = await query(
      `SELECT column_name FROM information_schema.columns
       WHERE table_schema = 'public' AND table_name = 'bridges'`
    );
    const cols = new Set(colRows.rows.map((r) => r.column_name));
    const hasLon = cols.has("lon");
    const hasLocation = cols.has("location");

    const cnt = await query("SELECT COUNT(*)::int AS c FROM bridges");
    const n = cnt.rows[0]?.c ?? 0;
    if (n > 0) {
      clearCapabilitiesCache();
      return;
    }

    if (hasLon) {
      await query(`
      INSERT INTO bridges (
        code, name, district, bridge_type, span_m, built_year, design_unit, description, model_path, lon, lat
      )
      VALUES
        ('SH-BR-001', '南浦大桥', '黄浦区', '斜拉桥', 846.00, 1991, '上海市政设计院', '示例（假设坐标为高德 GCJ-02，接口会转 WGS84）', '/models/SH-BR-001/tileset.json', 121.499, 31.210),
        ('SH-BR-002', '杨浦大桥', '杨浦区', '斜拉桥', 602.00, 1993, '上海市政设计院', '示例（假设坐标为高德 GCJ-02，接口会转 WGS84）', '/models/SH-BR-002/tileset.json', 121.548, 31.259),
        ('SH-BR-003', '卢浦大桥', '黄浦区', '拱桥', 550.00, 2003, '上海现代设计集团', '示例（假设坐标为高德 GCJ-02，接口会转 WGS84）', '/models/SH-BR-003/tileset.json', 121.472, 31.198)
      ON CONFLICT (code) DO NOTHING
    `);
      console.log("migrate: 已补种 3 条示例桥梁（lon/lat 模式）");
      clearCapabilitiesCache();
      return;
    }

    if (hasLocation) {
      await query(`
      INSERT INTO bridges (
        code, name, district, bridge_type, span_m, built_year, design_unit, description, model_path, location
      )
      VALUES
        ('SH-BR-001', '南浦大桥', '黄浦区', '斜拉桥', 846.00, 1991, '上海市政设计院', '示例（假设坐标为高德 GCJ-02，接口会转 WGS84）', '/models/SH-BR-001/tileset.json', ST_GeogFromText('POINT(121.499 31.210)')),
        ('SH-BR-002', '杨浦大桥', '杨浦区', '斜拉桥', 602.00, 1993, '上海市政设计院', '示例（假设坐标为高德 GCJ-02，接口会转 WGS84）', '/models/SH-BR-002/tileset.json', ST_GeogFromText('POINT(121.548 31.259)')),
        ('SH-BR-003', '卢浦大桥', '黄浦区', '拱桥', 550.00, 2003, '上海现代设计集团', '示例（假设坐标为高德 GCJ-02，接口会转 WGS84）', '/models/SH-BR-003/tileset.json', ST_GeogFromText('POINT(121.472 31.198)'))
      ON CONFLICT (code) DO NOTHING
    `);
      console.log("migrate: 已补种 3 条示例桥梁（PostGIS location 模式）");
      clearCapabilitiesCache();
      return;
    }

    console.warn("migrate: bridges 表无 lon/lat 也无 location 列，无法自动补种");
  } catch (e) {
    console.error("migrate failed:", e?.message || e);
    throw e;
  }
}
