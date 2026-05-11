import express from "express";
import { query } from "../db.js";
import { authRequired } from "../auth.js";
import { getDbCapabilities } from "../capabilities.js";
import { convertToWgs84 } from "../coords.js";

const router = express.Router();

function normalizeLonLat(row) {
  // 优先使用人工校准的 WGS84 坐标
  const wgsLon = row.wgs_lon ?? row.wgsLon;
  const wgsLat = row.wgs_lat ?? row.wgsLat;
  if (wgsLon != null && wgsLat != null) {
    const lonW = Number(wgsLon);
    const latW = Number(wgsLat);
    if (Number.isFinite(lonW) && Number.isFinite(latW) && Math.abs(lonW) <= 180 && Math.abs(latW) <= 90) {
      return { ...row, lon: lonW, lat: latW, coordSource: "wgs84(calibrated)" };
    }
  }

  const lon0 = Number(row.lon);
  const lat0 = Number(row.lat);
  if (!Number.isFinite(lon0) || !Number.isFinite(lat0)) return row;

  let lon = lon0;
  let lat = lat0;

  // 常见导入错误：经纬度写反（lon 在 [-90,90] 且 lat 在 (90,180]）
  // 对中国范围尤其常见：lon≈121, lat≈31；如果 lon≈31, lat≈121 则需要交换
  const maybeSwapped =
    Math.abs(lon) <= 90 &&
    Math.abs(lat) > 90 &&
    Math.abs(lat) <= 180;

  if (maybeSwapped) {
    [lon, lat] = [lat, lon];
  }

  // 基本合法性兜底：超范围则不改（让前端/用户发现数据问题）
  if (Math.abs(lon) > 180 || Math.abs(lat) > 90) return row;

  // 默认按高德 GCJ-02 入库/台账常见；若你已是 WGS84，在 .env 设 COORD_SOURCE=wgs84
  const source = process.env.COORD_SOURCE || "gcj02";
  const wgs = convertToWgs84(lon, lat, source);
  return { ...row, lon: wgs.lon, lat: wgs.lat, coordSource: source };
}

router.get("/", authRequired, async (req, res) => {
  try {
    const caps = await getDbCapabilities();
    const page = Number(req.query.page || 1);
    const pageSize = Number(req.query.pageSize || 10);
    const offset = (page - 1) * pageSize;
    const keyword = (req.query.keyword || "").trim();
    const district = (req.query.district || "").trim();

    const where = [];
    const params = [];
    let idx = 1;

    if (keyword) {
      where.push(`(name ILIKE $${idx} OR code ILIKE $${idx})`);
      params.push(`%${keyword}%`);
      idx += 1;
    }
    if (district) {
      where.push(`district = $${idx}`);
      params.push(district);
      idx += 1;
    }

    const whereSql = where.length ? `WHERE ${where.join(" AND ")}` : "";

    const listSql =
      caps.mode === "postgis"
        ? `
      SELECT id, code, name, district, bridge_type, span_m, built_year,
             ST_X(location::geometry) AS lon,
             ST_Y(location::geometry) AS lat,
             wgs_lon, wgs_lat
      FROM bridges
      ${whereSql}
      ORDER BY id
      LIMIT $${idx} OFFSET $${idx + 1}
    `
        : `
      SELECT id, code, name, district, bridge_type, span_m, built_year,
             lon, lat, wgs_lon, wgs_lat
      FROM bridges
      ${whereSql}
      ORDER BY id
      LIMIT $${idx} OFFSET $${idx + 1}
    `;
    const countSql = `SELECT COUNT(*)::int AS total FROM bridges ${whereSql}`;

    const listParams = [...params, pageSize, offset];
    const [listResult, countResult] = await Promise.all([
      query(listSql, listParams),
      query(countSql, params),
    ]);

    return res.json({
      page,
      pageSize,
      total: countResult.rows[0].total,
      records: listResult.rows.map(normalizeLonLat),
    });
  } catch (error) {
    return res.status(500).json({ message: "Fetch bridge list failed", detail: error.message });
  }
});

router.get("/:id", authRequired, async (req, res) => {
  try {
    const caps = await getDbCapabilities();
    const sql =
      caps.mode === "postgis"
        ? `
      SELECT id, code, name, district, bridge_type, span_m, built_year, design_unit,
             photos, description, model_path,
             ST_X(location::geometry) AS lon,
             ST_Y(location::geometry) AS lat,
             wgs_lon, wgs_lat
      FROM bridges
      WHERE id = $1
      `
        : `
      SELECT id, code, name, district, bridge_type, span_m, built_year, design_unit,
             photos, description, model_path,
             lon, lat, wgs_lon, wgs_lat
      FROM bridges
      WHERE id = $1
      `;

    const result = await query(sql, [req.params.id]);
    const bridge = result.rows[0];
    if (!bridge) return res.status(404).json({ message: "Bridge not found" });
    return res.json(normalizeLonLat(bridge));
  } catch (error) {
    return res.status(500).json({ message: "Fetch bridge detail failed", detail: error.message });
  }
});

router.post("/spatial/search", authRequired, async (req, res) => {
  try {
    const caps = await getDbCapabilities();
    const { minLon, minLat, maxLon, maxLat } = req.body;
    if ([minLon, minLat, maxLon, maxLat].some((v) => typeof v !== "number")) {
      return res.status(400).json({ message: "BBox values must be numbers" });
    }

    const sql =
      caps.mode === "postgis"
        ? `
      SELECT id, code, name, district, bridge_type,
             ST_X(location::geometry) AS lon,
             ST_Y(location::geometry) AS lat,
             wgs_lon, wgs_lat
      FROM bridges
      WHERE ST_Within(location, ST_MakeEnvelope($1, $2, $3, $4, 4326)::geography)
      ORDER BY id
      `
        : `
      SELECT id, code, name, district, bridge_type,
             lon, lat, wgs_lon, wgs_lat
      FROM bridges
      WHERE lon BETWEEN $1 AND $3 AND lat BETWEEN $2 AND $4
      ORDER BY id
      `;

    const result = await query(sql, [minLon, minLat, maxLon, maxLat]);

    return res.json({ count: result.rowCount, records: result.rows.map(normalizeLonLat) });
  } catch (error) {
    return res.status(500).json({ message: "Spatial search failed", detail: error.message });
  }
});

// 人工校准：在卫星图上点选真实位置，写入 wgs_lon/wgs_lat
router.put("/:id/coords", authRequired, async (req, res) => {
  try {
    if (req.user?.role !== "admin") {
      return res.status(403).json({ message: "Forbidden" });
    }

    const id = Number(req.params.id);
    const lon = Number(req.body?.lon);
    const lat = Number(req.body?.lat);
    if (!Number.isFinite(id) || !Number.isFinite(lon) || !Number.isFinite(lat)) {
      return res.status(400).json({ message: "id/lon/lat must be numbers" });
    }
    if (Math.abs(lon) > 180 || Math.abs(lat) > 90) {
      return res.status(400).json({ message: "lon/lat out of range" });
    }

    await query(
      "UPDATE bridges SET wgs_lon = $1, wgs_lat = $2, updated_at = NOW() WHERE id = $3",
      [lon, lat, id]
    );

    const result = await query(
      "SELECT id, code, name, district, bridge_type, lon, lat, wgs_lon, wgs_lat FROM bridges WHERE id = $1",
      [id]
    );
    const bridge = result.rows[0];
    return res.json({ ok: true, bridge: normalizeLonLat(bridge) });
  } catch (error) {
    return res.status(500).json({ message: "Update coords failed", detail: error.message });
  }
});

export default router;
