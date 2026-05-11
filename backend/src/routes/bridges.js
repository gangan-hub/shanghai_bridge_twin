import express from "express";
import { query } from "../db.js";
import { authRequired } from "../auth.js";
import { getDbCapabilities } from "../capabilities.js";
import { convertToWgs84, bd09ToWgs84 } from "../coords.js";
import path from "path";
import fs from "fs";
import { execFile } from "child_process";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, "..", "..", "..");
const SHANGHAI_XLSX = path.join(
  PROJECT_ROOT,
  "ai_models_flow",
  "shanghai_data",
  "shanghaidata_x.xlsx"
);

// 上海路网邻接矩阵（放在 ai_models_flow/shanghai_data/shanghai_a.npy）
const SHANGHAI_ADJ_NPY = path.join(
  PROJECT_ROOT,
  "ai_models_flow",
  "shanghai_data",
  "shanghai_a.npy"
);

// 上海路网链接矩阵 CSV（ai_models_flow/shanghai_data/generate_acc_shanghai/link_matrix_shanghai.csv）
const LINK_MATRIX_CSV = path.join(
  PROJECT_ROOT,
  "ai_models_flow",
  "shanghai_data",
  "generate_acc_shanghai",
  "link_matrix_shanghai.csv"
);

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
    const page = Math.max(1, parseInt(req.query.page || "1", 10));
    const pageSize = Math.min(5000, Math.max(1, parseInt(req.query.pageSize || "10", 10)));
    const offset = (page - 1) * pageSize;
    const keyword = (req.query.keyword || "").trim();
    const district = (req.query.district || "").trim();
    const bridgeType = (req.query.bridge_type || "").trim();

    // Discover actual columns to avoid referencing non-existent ones
    const colRes = await query(
      `SELECT column_name FROM information_schema.columns WHERE table_name = 'bridges'`,
    );
    const colSet = new Set(colRes.rows.map((r) => r.column_name));
    const wantCols = [
      "id", "code", "name", "district", "bridge_type", "span_m", "built_year",
      "wgs_lon", "wgs_lat", "bd_lon", "bd_lat",
      "node_0base", "display_idx", "func_name", "road_name", "road_class",
      "lanes", "poi_flow", "typecode",
    ];
    const safeCols = wantCols.filter((c) => colSet.has(c));

    const caps = await getDbCapabilities();
    const hasPostGIS = caps.mode === "postgis" && colSet.has("location");

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
    if (bridgeType) {
      where.push(`bridge_type = $${idx}`);
      params.push(bridgeType);
      idx += 1;
    }

    const whereSql = where.length ? `WHERE ${where.join(" AND ")}` : "";

    let listSql;
    if (hasPostGIS) {
      const selectCols = [
        ...safeCols.filter((c) => c !== "id" && c !== "lon" && c !== "lat"),
        "ST_X(location::geometry) AS lon",
        "ST_Y(location::geometry) AS lat",
      ];
      if (safeCols.includes("id")) selectCols.unshift("id");
      listSql = `
        SELECT ${selectCols.join(", ")}
        FROM bridges
        ${whereSql}
        ORDER BY node_0base NULLS LAST, id
        LIMIT $${idx} OFFSET $${idx + 1}
      `;
    } else {
      const selectCols = safeCols.filter((c) => c !== "id");
      if (safeCols.includes("id")) selectCols.unshift("id");
      listSql = `
        SELECT ${selectCols.join(", ")}
        FROM bridges
        ${whereSql}
        ORDER BY CASE WHEN node_0base IS NULL THEN 1 ELSE 0 END, node_0base, id
        LIMIT $${idx} OFFSET $${idx + 1}
      `;
    }

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

router.get("/:id", authRequired, async (req, res, next) => {
  try {
    const id = Number(req.params.id);
    if (!Number.isInteger(id) || id <= 0) {
      // 非数字路径（如 /reload_from_xlsx）交给后续路由处理
      return next();
    }
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

/* ============================================================
 * 🔄 /bridges/reload_from_xlsx  →  从 shanghaidata_x.xlsx 实时重加载
 *   - 读取百度 BD09 坐标（x=经度, y=纬度）
 *   - 转换 BD09 → GCJ02 → WGS84
 *   - node 列 + 1 = 节点显示序号 display_idx
 *   - 批量 UPSERT 到 bridges 表（以 code/id 为键）
 *   - 返回更新后的节点列表 + 统计
 * ============================================================ */
router.get("/reload_from_xlsx", authRequired, async (req, res) => {
  try {
    if (!fs.existsSync(SHANGHAI_XLSX)) {
      return res.status(404).json({
        message: "shanghaidata_x.xlsx 不存在",
        path: SHANGHAI_XLSX,
      });
    }

    // 用系统 Python 读 xlsx（转 JSON stdout，Node 不用装 pandas/openpyxl）
    const pyBin = "C:\\Program Files\\Python312\\python.exe";
    const pySrc = `
import sys, json, pandas as pd, math, os
x_pi = 3.14159265358979324 * 3000.0 / 180.0
pi   = 3.1415926535897932384626
a    = 6378245.0
ee   = 0.00669342162296594323
def tl(x,y):
    r=-100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*math.sqrt(abs(x))
    r+=(20*math.sin(6*x*pi)+20*math.sin(2*x*pi))*2/3
    r+=(20*math.sin(y*pi)+40*math.sin(y/3*pi))*2/3
    r+=(160*math.sin(y/12*pi)+320*math.sin(y*pi/30))*2/3
    return r
def tn(x,y):
    r=300+x+2*y+0.1*x*x+0.1*x*y+0.1*math.sqrt(abs(x))
    r+=(20*math.sin(6*x*pi)+20*math.sin(2*x*pi))*2/3
    r+=(20*math.sin(x*pi)+40*math.sin(x/3*pi))*2/3
    r+=(150*math.sin(x/12*pi)+300*math.sin(x/30*pi))*2/3
    return r
def bd_gcj(blon,blat):
    x,y = blon-0.0065, blat-0.006
    z=math.sqrt(x*x+y*y)-0.00002*math.sin(y*x_pi)
    th=math.atan2(y,x)-0.000003*math.cos(x*x_pi)
    return z*math.cos(th), z*math.sin(th)
def gcj_wgs(ln,lt):
    dlat,dlon=tl(ln-105,lt-35),tn(ln-105,lt-35)
    rl=lt/180*pi; mg=math.sin(rl); mg=1-ee*mg*mg; sg=math.sqrt(mg)
    dlat=(dlat*180)/(((a*(1-ee))/(mg*sg))*pi)
    dlon=(dlon*180)/((a/sg*math.cos(rl))*pi)
    return ln*2-(ln+dlon), lt*2-(lt+dlat)
def bd_wgs(blon,blat):
    g0,g1 = bd_gcj(blon,blat); return gcj_wgs(g0,g1)

p = r"${SHANGHAI_XLSX.replace(/\\\\/g, '\\\\\\\\')}"
df = pd.read_excel(p)
rows=[]
for i,r in df.iterrows():
    try:
        node = int(float(r['node'])) if 'node' in df.columns and pd.notna(r.get('node')) else i
    except Exception:
        node = i
    try:
        display_idx = node + 1
    except Exception:
        display_idx = i + 1
    def v(c, default=None):
        if c not in df.columns: return default
        x = r[c]
        if pd.isna(x): return default
        if isinstance(x,str):
            s = x.strip()
            return s if s else default
        return x
    name = str(v('name', f'节点_{display_idx}'))
    bx = v('x'); by = v('y')
    wgs_lon=None; wgs_lat=None; bd_lon=None; bd_lat=None
    try:
        bx=float(bx); by=float(by)
        if (-180<=bx<=180 and -90<=by<=90):
            bd_lon=bx; bd_lat=by
            wgs_lon, wgs_lat = bd_wgs(bx, by)
    except Exception:
        pass
    rows.append({
        'node_0base': node, 'display_idx': display_idx,
        'code': str(v('id', f'SH{str(node).zfill(5)}'))[:50],
        'name': name,
        'district': str(v('adname',''))[:60],
        'bridge_type': str(v('桥隧类型',''))[:30],
        'road_class': str(v('road_class',''))[:20],
        'lanes': v('车道数'),
        'func_name': str(v('分工',''))[:60],
        'road_name': str(v('roadname',''))[:120],
        'poi_flow': v('poi'),
        'bd_lon': bd_lon, 'bd_lat': bd_lat,
        'lon': wgs_lon, 'lat': wgs_lat,
        'wgs_lon': wgs_lon, 'wgs_lat': wgs_lat,
    })
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps(rows, ensure_ascii=False, allow_nan=False))
`;

    const rows = await new Promise((resolve, reject) => {
      const bufs = [];
      const errs = [];
      const child = execFile(pyBin, ["-c", pySrc], {
        timeout: 120_000,
        maxBuffer: 80 * 1024 * 1024,
        env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
      });
      child.stdout.on("data", (d) => bufs.push(d));
      child.stderr.on("data", (d) => errs.push(d));
      const toText = (chunks) => {
        if (!chunks.length) return "";
        if (Buffer.isBuffer(chunks[0])) return Buffer.concat(chunks).toString("utf-8");
        return chunks.join("");
      };
      child.on("close", (code) => {
        if (code === 0) {
          try { resolve(JSON.parse(toText(bufs))); }
          catch (e) { reject(new Error("xlsx parse json invalid: " + e.message)); }
        } else {
          reject(new Error(
            `python exit ${code}: ` +
            toText(errs).slice(0, 600)
          ));
        }
      });
      child.on("error", reject);
    });

    // --- 批量 UPSERT 到 bridges 表 ---
    // 假设 bridges 表唯一键是 code（若不存在则按 id 兜底）。
    let updated = 0, inserted = 0, skipped = 0;

    for (const r of rows) {
      if (r.lon == null || r.lat == null) { skipped++; continue; }
      try {
        // 1) 看 code 是否存在
        const ex = await query("SELECT id FROM bridges WHERE code = $1 LIMIT 1", [r.code]);
        if (ex.rows.length > 0) {
          await query(`
            UPDATE bridges SET
              name        = $1,
              district    = $2,
              bridge_type = $3,
              road_class  = $4,
              lanes       = $5,
              func_name   = $6,
              road_name   = $7,
              poi_flow    = $8,
              lon         = $9,
              lat         = $10,
              wgs_lon     = $11,
              wgs_lat     = $12,
              bd_lon      = $13,
              bd_lat      = $14,
              node_0base  = $15,
              display_idx = $16,
              updated_at  = NOW()
            WHERE id = $17
          `, [
            r.name, r.district, r.bridge_type, r.road_class, r.lanes,
            r.func_name, r.road_name, r.poi_flow,
            r.lon, r.lat, r.wgs_lon, r.wgs_lat, r.bd_lon, r.bd_lat,
            r.node_0base, r.display_idx,
            ex.rows[0].id,
          ]);
          updated++;
        } else {
          await query(`
            INSERT INTO bridges
              (code, name, district, bridge_type, road_class, lanes, func_name, road_name,
               poi_flow, lon, lat, wgs_lon, wgs_lat, bd_lon, bd_lat, node_0base, display_idx)
            VALUES
              ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
          `, [
            r.code, r.name, r.district, r.bridge_type, r.road_class, r.lanes,
            r.func_name, r.road_name, r.poi_flow,
            r.lon, r.lat, r.wgs_lon, r.wgs_lat, r.bd_lon, r.bd_lat,
            r.node_0base, r.display_idx,
          ]);
          inserted++;
        }
      } catch (e) {
        // 某一行失败不影响整体，统计 skipped
        skipped++;
      }
    }

    return res.json({
      ok: true,
      reloaded: rows.length,
      updated, inserted, skipped,
      xlsx_path: SHANGHAI_XLSX,
      xlsx_mtime: new Date(fs.statSync(SHANGHAI_XLSX).mtime).toISOString(),
      sample: rows.slice(0, 3),
    });
  } catch (error) {
    return res.status(500).json({
      message: "reload_from_xlsx 失败",
      detail: error.message || String(error),
    });
  }
});

// ============================================================
//  GET /api/bridges/load_edges
//  从 shanghai_a.npy 实时读取邻接矩阵，返回边列表（拓扑连接）
//  返回格式：{ edges: [{source, target, weight}], matrixShape, edgeCount, npyMtime }
//  前端拿到后直接喂给 CesiumMap.renderTopology({ links: edges })
// ============================================================
router.get("/load_edges", authRequired, async (req, res) => {
  const t0 = Date.now();
  console.log("[load_edges] request received");

  try {
    // 1. 检查文件是否存在
    if (!fs.existsSync(SHANGHAI_ADJ_NPY)) {
      console.error("[load_edges] npy file not found:", SHANGHAI_ADJ_NPY);
      return res.status(404).json({
        error: "邻接矩阵文件不存在",
        path: SHANGHAI_ADJ_NPY,
        hint: `请将 shanghai_a.npy 放到 ${SHANGHAI_ADJ_NPY}`,
      });
    }

    const npyMtime = new Date(fs.statSync(SHANGHAI_ADJ_NPY).mtime).toISOString();

    // 2. 用 Python 子进程读取 .npy，提取非零元素作为边列表
    const pySrc = `
import sys, json, os
try:
    import numpy as np
except ImportError:
    sys.stderr.write("ERROR: numpy not installed\\n")
    sys.exit(1)

npy_path = r"${SHANGHAI_ADJ_NPY.replace(/\\\\/g, '\\\\\\\\')}"

try:
    A = np.load(npy_path)
except Exception as e:
    sys.stderr.write(f"ERROR: cannot load npy: {e}\\n")
    sys.exit(1)

rows, cols = A.nonzero()
edges = []
for i in range(len(rows)):
    s = int(rows[i])
    t = int(cols[i])
    w = float(A[s, t])
    # 只保留上三角（去重无向边）
    if s < t:
        edges.append({"source": s, "target": t, "weight": w})

result = {
    "edges": edges,
    "edgeCount": len(edges),
    "matrixShape": list(A.shape),
    "totalNonZero": int(A.nnz) if hasattr(A, 'nnz') else int((A != 0).sum()),
}
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, allow_nan=False))
`;

    const { execFile } = await import("child_process");

    const edgesData = await new Promise((resolve, reject) => {
      execFile(
        "C:\\Program Files\\Python312\\python.exe",
        ["-c", pySrc],
        { maxBuffer: 1024 * 1024 * 10, timeout: 60000 },
        (err, stdout, stderr) => {
          if (err) {
            console.error("[load_edges] python error:", stderr || err.message);
            reject(new Error(`Python 执行失败: ${stderr || err.message}`));
            return;
          }
          try {
            resolve(JSON.parse(stdout.trim()));
          } catch (e) {
            console.error("[load_edges] JSON parse error:", stdout.slice(0, 300));
            reject(new Error("Python 输出解析失败"));
          }
        }
      );
    });

    console.log(
      `[load_edges] loaded: shape=${edgesData.matrixShape}, ` +
      `edges=${edgesData.edgeCount}, totalNonZero=${edgesData.totalNonZero}, ` +
      `elapsed=${Date.now() - t0}ms`
    );

    res.json({
      success: true,
      edges: edgesData.edges,
      edgeCount: edgesData.edgeCount,
      matrixShape: edgesData.matrixShape,
      totalNonZero: edgesData.totalNonZero,
      npy_path: SHANGHAI_ADJ_NPY,
      npy_mtime: npyMtime,
      elapsed_ms: Date.now() - t0,
    });
  } catch (error) {
    console.error("[load_edges] error:", error);
    res.status(500).json({
      error: "读取邻接矩阵失败",
      detail: error.message || String(error),
    });
  }
});

// ============================================================
//  GET /api/bridges/load_link_matrix
//  从 link_matrix_shanghai.csv 实时读取链接矩阵，返回边列表 + 统计信息
//  矩阵为 332×332 CSV，浮点权重值，>0 表示有连接，=0 不连接
//  返回格式：{ edges, edgeCount, matrixShape, totalNodes, connectedPairs, csv_path, csv_mtime }
// ============================================================
router.get("/load_link_matrix", authRequired, async (req, res) => {
  const t0 = Date.now();
  console.log("[load_link_matrix] request received");

  try {
    // 1. 文件路径校验
    if (!fs.existsSync(LINK_MATRIX_CSV)) {
      console.error("[load_link_matrix] CSV file not found:", LINK_MATRIX_CSV);
      return res.status(404).json({
        error: "链接矩阵文件不存在",
        path: LINK_MATRIX_CSV,
        hint: `请将 link_matrix_shanghai.csv 放到 ${LINK_MATRIX_CSV}`,
      });
    }

    const csvMtime = new Date(fs.statSync(LINK_MATRIX_CSV).mtime).toISOString();

    // 2. 用 Python 子进程读取 CSV 矩阵，提取连接边
    const pySrc = `
import sys, json, csv, os

csv_path = r"${LINK_MATRIX_CSV.replace(/\\\\/g, '\\\\\\\\')}"

try:
    # 读取 CSV 矩阵
    matrix = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # 跳过表头行（空 + 列索引 0~331）
        for row in reader:
            # 每行第一个值是行索引，后面 332 个是数据值
            if len(row) < 2:
                continue
            values = [float(v) for v in row[1:]]  # 跳过行索引列
            matrix.append(values)

    n = len(matrix)  # 总节点数（行数）
    if n == 0:
        sys.stderr.write("ERROR: matrix is empty\\n")
        sys.exit(1)

    m = len(matrix[0]) if n > 0 else 0  # 列数
    if n != m:
        sys.stderr.write(f"WARNING: matrix is not square: {n}x{m}\\n")

    # 遍历上三角（i < j），提取 value > 0 的连接边，排除对角线
    edges = []
    for i in range(n):
        for j in range(i + 1, min(m, n)):
            val = matrix[i][j]
            if val > 0:
                edges.append({
                    "source": i,
                    "target": j,
                    "weight": round(val, 6)
                })

    # 统计信息
    total_edges = len(edges)
    # 统计有连接的节点对（source, target 列表）
    connected_pairs = [{"source": e["source"], "target": e["target"], "weight": e["weight"]} for e in edges]

    result = {
        "edges": edges,
        "edgeCount": total_edges,
        "matrixShape": [n, m],
        "totalNodes": n,
        "connectedPairs": connected_pairs,
    }
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))

except Exception as e:
    sys.stderr.write(f"ERROR: {e}\\n")
    sys.exit(1)
`;

    const edgesData = await new Promise((resolve, reject) => {
      execFile(
        "C:\\Program Files\\Python312\\python.exe",
        ["-c", pySrc],
        { maxBuffer: 1024 * 1024 * 20, timeout: 120000 },
        (err, stdout, stderr) => {
          if (err) {
            console.error("[load_link_matrix] python error:", stderr || err.message);
            reject(new Error(`Python 执行失败: ${stderr || err.message}`));
            return;
          }
          try {
            resolve(JSON.parse(stdout.trim()));
          } catch (e) {
            console.error("[load_link_matrix] JSON parse error:", stdout.slice(0, 500));
            reject(new Error("Python 输出解析失败"));
          }
        }
      );
    });

    console.log(
      `[load_link_matrix] loaded: shape=${edgesData.matrixShape}, ` +
      `nodes=${edgesData.totalNodes}, edges=${edgesData.edgeCount}, ` +
      `elapsed=${Date.now() - t0}ms`
    );

    res.json({
      success: true,
      edges: edgesData.edges,
      edgeCount: edgesData.edgeCount,
      matrixShape: edgesData.matrixShape,
      totalNodes: edgesData.totalNodes,
      connectedPairs: edgesData.connectedPairs,
      csv_path: LINK_MATRIX_CSV,
      csv_mtime: csvMtime,
      elapsed_ms: Date.now() - t0,
    });
  } catch (error) {
    console.error("[load_link_matrix] error:", error);
    res.status(500).json({
      error: "读取链接矩阵失败",
      detail: error.message || String(error),
    });
  }
});

/* =====================================================
 * 统一数据加载端点 —— 调用 file_reader_service.py
 * 一次性读取 xlsx（节点坐标 + 元数据）和 csv（链接矩阵边）
 * 自动更新数据库坐标并返回边数据供前端渲染拓扑连线
 * ===================================================== */
router.post("/load_all_data", authRequired, async (req, res) => {
  try {
    const xlsxPath = req.body?.xlsx_path || SHANGHAI_XLSX;
    const csvPath = req.body?.csv_path || LINK_MATRIX_CSV;

    /* 文件存在性检查 */
    const xlsxExists = fs.existsSync(xlsxPath);
    const csvExists = fs.existsSync(csvPath);
    if (!xlsxExists && !csvExists) {
      return res.status(404).json({
        message: "xlsx 和 csv 文件均未找到",
        xlsx_path: xlsxPath,
        csv_path: csvPath,
      });
    }

    /* 调用 file_reader_service.py 统一读取 */
    const scriptPath = path.join(__dirname, "..", "file_reader_service.py");
    const mode = xlsxExists && csvExists ? "all" : xlsxExists ? "xlsx" : "csv";

    const pyResult = await new Promise((resolve, reject) => {
      const proc = execFile(
        "C:\\Program Files\\Python312\\python.exe",
        [scriptPath, "--mode", mode, "--xlsx", xlsxPath, "--csv", csvPath],
        { maxBuffer: 100 * 1024 * 1024, timeout: 120_000 },
        (err, stdout, stderr) => {
          if (err) reject(new Error(`Python 子进程错误: ${stderr || err.message}`));
          else resolve(stdout);
        }
      );
      proc.on("error", (e) => reject(new Error(`无法启动 Python: ${e.message}`)));
    });

    const result = JSON.parse(pyResult);
    if (result.error) {
      return res.status(500).json({ message: result.error });
    }

    /* 若有 xlsx 节点数据 → 更新数据库 WGS84 坐标 */
    let updated = 0;
    let skipped = 0;
    const nodes = result.xlsx?.nodes || [];

    for (const node of nodes) {
      const nodeId = node.node_0base;
      const wgsLon = node.wgs84_lng;
      const wgsLat = node.wgs84_lat;
      if (
        nodeId == null ||
        wgsLon == null ||
        wgsLat == null ||
        !Number.isFinite(wgsLon) ||
        !Number.isFinite(wgsLat)
      ) {
        skipped++;
        continue;
      }
      const updateResult = await query(
        `UPDATE bridges
         SET wgs_lon = $1, wgs_lat = $2, coord_source = 'auto_xlsx_bd09'
         WHERE node_0base = $3`,
        [wgsLon, wgsLat, nodeId]
      );
      if (updateResult.rowCount > 0) updated++;
    }

    /* 检查 npy 文件是否也存在（前端可合并使用） */
    const npyExists = fs.existsSync(SHANGHAI_ADJ_NPY);

    res.json({
      reloaded: result.xlsx?.nodeCount || 0,
      updated,
      inserted: 0,
      skipped,
      xlsx_mtime: result.xlsx?.xlsx_mtime || null,
      xlsx_path: xlsxPath,
      edges: result.csv?.edges || [],
      csvEdgeCount: result.csv?.edgeCount || 0,
      csvMatrixShape: result.csv?.matrixShape || null,
      csv_path: csvPath,
      csv_mtime: result.csv?.csv_mtime || null,
      npy_exists: npyExists,
      npy_path: SHANGHAI_ADJ_NPY,
      mode: result.mode,
    });
  } catch (e) {
    const statusCode = e.message?.includes("未找到") || e.message?.includes("不存在") ? 404 : 500;
    res.status(statusCode).json({
      message: "统一数据加载失败",
      error: e.message,
    });
  }
});

export default router;
