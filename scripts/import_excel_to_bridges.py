#!/usr/bin/env python3
"""
Import Excel POI data into bridges table.
Usage: python import_excel_to_bridges.py

Excel 22 列（全为百度 BD-09 坐标）:
  node, typecode, name, x, y, x_1, y_1, x_2, y_2,
  congestion_value, poi, congestion, index, free-flow speed, jam density,
  id, adname, roadname, roadname_origin, 桥隧类型, road_class, 车道数

坐标语义:
  x/y         -> 节点中点坐标
  x_1/y_1     -> 桥梁首坐标
  x_2/y_2     -> 桥梁尾坐标
  三组坐标均从百度 BD-09 转换为 WGS84 后写入数据库。
"""
import sys
import os
import json
import math
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

# --- 配置 ---
EXCEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "ai_models_flow", "shanghai_data", "shanghaidata_x.xlsx"
)
SHEET_NAME = 0
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "database": "bridge_twin",
    "user": "postgres",
    "password": "123456",
}

# ==================== 坐标转换：BD-09 -> GCJ-02 -> WGS84 ====================
_PI = math.pi
_A = 6378245.0
_EE = 0.00669342162296594323


def _transform_lat_gcj(lng, lat):
    ret = (-100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat +
           0.1 * lng * lat + 0.2 * math.sqrt(abs(lng)))
    ret += (20.0 * math.sin(6.0 * lng * _PI) +
            20.0 * math.sin(2.0 * lng * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * _PI) +
            40.0 * math.sin(lat / 3.0 * _PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * _PI) +
            320.0 * math.sin(lat * _PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng_gcj(lng, lat):
    ret = (300.0 + lng + 2.0 * lat + 0.1 * lng * lng +
           0.1 * lng * lat + 0.1 * math.sqrt(abs(lng)))
    ret += (20.0 * math.sin(6.0 * lng * _PI) +
            20.0 * math.sin(2.0 * lng * _PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * _PI) +
            40.0 * math.sin(lng / 3.0 * _PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * _PI) +
            300.0 * math.sin(lng / 30.0 * _PI)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lng, lat):
    """GCJ-02 坐标转 WGS84 坐标"""
    try:
        lng, lat = float(lng), float(lat)
    except (TypeError, ValueError):
        return None, None
    dlat = _transform_lat_gcj(lng - 105.0, lat - 35.0)
    dlng = _transform_lng_gcj(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * _PI
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * _PI)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * _PI)
    wgs_lat = lat - dlat
    wgs_lng = lng - dlng
    return round(wgs_lng, 6), round(wgs_lat, 6)


def bd09_to_gcj02(lng, lat):
    """BD-09 坐标转 GCJ-02 坐标"""
    try:
        lng, lat = float(lng), float(lat)
    except (TypeError, ValueError):
        return None, None
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _PI * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _PI * 3000.0 / 180.0)
    gcj_lng = z * math.cos(theta)
    gcj_lat = z * math.sin(theta)
    return gcj_lng, gcj_lat


def bd09_to_wgs84(lng, lat):
    """BD-09 坐标直接转 WGS84 坐标"""
    gcj_lng, gcj_lat = bd09_to_gcj02(lng, lat)
    if gcj_lng is None or gcj_lat is None:
        return None, None
    return gcj02_to_wgs84(gcj_lng, gcj_lat)


def _coord(v):
    """把 Excel 单元格安全转成 float，无效返回 None。"""
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


# 建表 DDL：覆盖 Excel 全部列 + 三组 WGS84 坐标 + 后端查询所需兜底列
CREATE_TABLE_STATEMENTS = [
    "DROP TABLE IF EXISTS bridges CASCADE;",
    """CREATE TABLE bridges (
        id              SERIAL PRIMARY KEY,
        code            VARCHAR(100),
        name            VARCHAR(200),
        district        VARCHAR(100),
        typecode        INTEGER,
        bridge_type     VARCHAR(100),
        road_name       VARCHAR(200),
        road_name_origin VARCHAR(200),
        road_class      VARCHAR(50),
        lanes           DOUBLE PRECISION,
        node_0base      INTEGER,
        display_idx     INTEGER,
        congestion_value DOUBLE PRECISION,
        congestion      DOUBLE PRECISION,
        free_flow_speed DOUBLE PRECISION,
        jam_density     DOUBLE PRECISION,
        poi_id          VARCHAR(100),
        poi_baidu_id    VARCHAR(100),
        -- 三组 WGS84 坐标
        lon             NUMERIC(10,6),
        lat             NUMERIC(10,6),
        lon_start       NUMERIC(10,6),
        lat_start       NUMERIC(10,6),
        lon_end         NUMERIC(10,6),
        lat_end         NUMERIC(10,6),
        wgs_lon         NUMERIC(10,6),
        wgs_lat         NUMERIC(10,6),
        -- 后端 /bridges 查询与 migrate.js 所需兜底列
        span_m          DOUBLE PRECISION,
        built_year      INTEGER,
        func_name       VARCHAR(100),
        poi_flow        VARCHAR(100),
        bd_lon          NUMERIC(10,6),
        bd_lat          NUMERIC(10,6),
        created_at      TIMESTAMP DEFAULT NOW(),
        updated_at      TIMESTAMP DEFAULT NOW()
    );""",
    "CREATE INDEX idx_bridges_node ON bridges(node_0base);",
    "CREATE INDEX idx_bridges_district ON bridges(district);",
    "CREATE INDEX idx_bridges_wgs ON bridges(wgs_lon, wgs_lat);",
]

# Excel 列名（真实存在）-> 数据库列名
COLUMN_MAP = {
    "node": "node_0base",
    "typecode": "typecode",
    "name": "name",
    "x": "lon",                      # 节点中点经度 (BD-09，稍后转 WGS84)
    "y": "lat",                      # 节点中点纬度 (BD-09，稍后转 WGS84)
    "x_1": "lon_start",              # 桥梁首经度 (BD-09，稍后转 WGS84)
    "y_1": "lat_start",              # 桥梁首纬度 (BD-09，稍后转 WGS84)
    "x_2": "lon_end",                # 桥梁尾经度 (BD-09，稍后转 WGS84)
    "y_2": "lat_end",                # 桥梁尾纬度 (BD-09，稍后转 WGS84)
    "congestion_value": "congestion_value",
    "poi": "poi_id",
    "congestion": "congestion",
    "index": "display_idx",
    "free-flow speed": "free_flow_speed",
    "jam density": "jam_density",
    "id": "poi_baidu_id",
    "adname": "district",
    "roadname": "road_name",
    "roadname_origin": "road_name_origin",
    "桥隧类型": "bridge_type",
    "road_class": "road_class",
    "车道数": "lanes",
}

# 数值列（需要按 float 读取写入，保证类型正确）
FLOAT_COLS = {
    "lon", "lat", "lon_start", "lat_start", "lon_end", "lat_end",
    "wgs_lon", "wgs_lat", "congestion_value", "congestion",
    "free_flow_speed", "jam_density", "lanes",
}
INT_COLS = {"node_0base", "typecode", "display_idx"}


def safe_val(v):
    """把 pandas 特殊类型转成 Python 原生类型，NaN/NaT 转 None。"""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        return v.item()
    return v


def main():
    print("=" * 60)
    print("  Excel → PostgreSQL bridges 全量导入工具")
    print("=" * 60)

    # ── 1. 读取 Excel ──────────────────────────────────────
    print(f"\n[1/6] 读取 Excel: {EXCEL_PATH}")
    if not os.path.exists(EXCEL_PATH):
        print(f"ERROR: 文件不存在 → {EXCEL_PATH}")
        sys.exit(1)

    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    except Exception as e:
        print(f"ERROR: 读取 Excel 失败 → {e}")
        sys.exit(1)

    print(f"  行数: {len(df)}, 列数: {len(df.columns)}")
    print(f"  列名: {list(df.columns)}")

    # 未映射列提醒
    unmapped = [c for c in df.columns if c not in COLUMN_MAP]
    if unmapped:
        print(f"WARNING: 以下 Excel 列未映射，将被忽略 → {unmapped}")

    expected_count = len(df)

    # 重命名列
    df = df.rename(columns=COLUMN_MAP)

    # ── 2. 三组坐标 BD-09 -> WGS84 转换 ─────────────────────
    print("\n[2/6] 坐标转换（BD-09 → WGS84）...")
    # 用于生成 code（后端搜索兼容）：优先 poi_baidu_id，否则按节点序号生成
    df["code"] = None

    # 三组坐标分别转换并生成结果列
    def convert_pair(row, lon_col, lat_col):
        bl = _coord(row.get(lon_col))
        bt = _coord(row.get(lat_col))
        if bl is not None and bt is not None:
            wl, wt = bd09_to_wgs84(bl, bt)
            return wl, wt
        return None, None

    wgs_lons = []
    wgs_lats = []
    lon_start_vals = []
    lat_start_vals = []
    lon_end_vals = []
    lat_end_vals = []
    converted = 0

    for _, row in df.iterrows():
        # 中点坐标
        ml, mt = convert_pair(row, "lon", "lat")
        # 首坐标
        sl, st = convert_pair(row, "lon_start", "lat_start")
        # 尾坐标
        el, et = convert_pair(row, "lon_end", "lat_end")

        if ml is not None and mt is not None:
            converted += 1

        wgs_lons.append(ml)
        wgs_lats.append(mt)
        lon_start_vals.append(sl)
        lat_start_vals.append(st)
        lon_end_vals.append(el)
        lat_end_vals.append(et)

    # 中点 WGS84 作为地图聚焦的核心坐标（后端 normalizeLonLat 优先读 wgs_lon/wgs_lat）
    df["wgs_lon"] = wgs_lons
    df["wgs_lat"] = wgs_lats
    df["lon"] = wgs_lons
    df["lat"] = wgs_lats
    df["lon_start"] = lon_start_vals
    df["lat_start"] = lat_start_vals
    df["lon_end"] = lon_end_vals
    df["lat_end"] = lat_end_vals

    print(f"  已转换中点 WGS84 坐标: {converted}/{expected_count}")

    # 生成 code：优先 poi_baidu_id，否则按节点序号补齐
    df["code"] = df.apply(
        lambda r: str(safe_val(r.get("poi_baidu_id")) or "").strip()
        if safe_val(r.get("poi_baidu_id")) is not None
        else f"SH-BR-{int(safe_val(r.get('node_0base')) or r.name)}",
        axis=1,
    )

    # ── 3. 组装写入列（对齐后端 wantCols 全量列） ──────────
    db_cols = [
        "code", "name", "district", "typecode", "bridge_type",
        "road_name", "road_name_origin", "road_class", "lanes",
        "node_0base", "display_idx", "congestion_value", "congestion",
        "free_flow_speed", "jam_density", "poi_id", "poi_baidu_id",
        "lon", "lat", "lon_start", "lat_start", "lon_end", "lat_end",
        "wgs_lon", "wgs_lat",
        # 兜底列：Excel 无数据，写入 NULL
        "span_m", "built_year", "func_name", "poi_flow", "bd_lon", "bd_lat",
    ]

    # ── 4. 连接数据库 ──────────────────────────────────────
    print(f"\n[3/6] 连接数据库: {DB_CONFIG['database']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        print("  连接成功")
    except psycopg2.Error as e:
        print(f"ERROR: 数据库连接失败 → {e}")
        sys.exit(1)

    try:
        cur = conn.cursor()

        # ── 5. 删除旧表并建新表 ────────────────────────────
        print("\n[4/6] 重建 bridges 表...")
        for stmt in CREATE_TABLE_STATEMENTS:
            cur.execute(stmt)
        conn.commit()
        print("  DROP + CREATE + INDEX 完成")

        # ── 6. 批量写入 ────────────────────────────────────
        print(f"\n[5/6] 批量写入 {expected_count} 条记录...")
        rows = []
        for _, row in df.iterrows():
            values = []
            for c in db_cols:
                if c not in df.columns:
                    values.append(None)
                    continue
                v = safe_val(row.get(c))
                if v is None:
                    values.append(None)
                elif c in INT_COLS:
                    try:
                        values.append(int(float(v)))
                    except (TypeError, ValueError):
                        values.append(None)
                elif c in FLOAT_COLS:
                    try:
                        values.append(float(v))
                    except (TypeError, ValueError):
                        values.append(None)
                else:
                    values.append(v)
            rows.append(tuple(values))

        insert_sql = f"""
            INSERT INTO bridges ({', '.join(db_cols)})
            VALUES %s
        """
        execute_values(cur, insert_sql, rows, page_size=500)
        conn.commit()
        print("  写入完成")

        # ── 7. 完整性校验 ──────────────────────────────────
        print("\n[6/6] 数据完整性校验...")
        cur.execute("SELECT COUNT(*) FROM bridges")
        actual_count = cur.fetchone()[0]
        print(f"  期望行数: {expected_count}, 实际行数: {actual_count}")

        # 坐标完整性
        cur.execute("SELECT COUNT(*) FROM bridges WHERE wgs_lon IS NOT NULL AND wgs_lat IS NOT NULL")
        coord_count = cur.fetchone()[0]
        print(f"  WGS84 坐标完整: {coord_count}/{actual_count}")

        # 首尾坐标完整性
        cur.execute("SELECT COUNT(*) FROM bridges WHERE lon_start IS NOT NULL AND lat_start IS NOT NULL")
        start_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bridges WHERE lon_end IS NOT NULL AND lat_end IS NOT NULL")
        end_count = cur.fetchone()[0]
        print(f"  首坐标完整: {start_count}/{actual_count}, 尾坐标完整: {end_count}/{actual_count}")

        # 各列 NULL 统计（只统计 Excel 有数据源的核心列）
        core_cols = [
            "name", "district", "typecode", "bridge_type", "road_name",
            "road_name_origin", "road_class", "lanes", "node_0base",
            "display_idx", "congestion_value", "congestion",
            "free_flow_speed", "jam_density", "poi_id", "poi_baidu_id",
            "lon", "lat", "lon_start", "lat_start", "lon_end", "lat_end",
            "wgs_lon", "wgs_lat",
        ]
        null_issues = []
        print("\n  各核心列 NULL 统计:")
        for col in core_cols:
            cur.execute(f'SELECT COUNT(*) FROM bridges WHERE "{col}" IS NULL')
            null_count = cur.fetchone()[0]
            if null_count > 0:
                null_issues.append((col, null_count))
                print(f"    {col}: {null_count} 个 NULL")
        if not null_issues:
            print("    全部核心列无 NULL")

        # 抽样验证
        cur.execute(
            "SELECT node_0base, name, lon, lat, lon_start, lat_start, lon_end, lat_end, wgs_lon, wgs_lat, bridge_type, district FROM bridges ORDER BY node_0base LIMIT 3"
        )
        print("\n  抽样（前3条）:")
        for r in cur.fetchall():
            print(f"    node={r[0]}, name={r[1]}")
            print(f"      中点=({r[2]},{r[3]}) 首=({r[4]},{r[5]}) 尾=({r[6]},{r[7]}) wgs=({r[8]},{r[9]}) type={r[10]} district={r[11]}")

        print("\n" + "=" * 60)
        if actual_count == expected_count and coord_count == expected_count and not null_issues:
            print("  导入成功！全部数据完整写入并通过校验。")
        else:
            print("  警告：数据校验未完全通过，请检查上方 NULL 统计。")
        print("=" * 60)

        cur.close()

        result = {
            "status": "ok" if (actual_count == expected_count and coord_count == expected_count) else "partial",
            "count": actual_count,
            "coord_converted": coord_count,
        }
        print(json.dumps(result, ensure_ascii=False))

    except psycopg2.Error as e:
        conn.rollback()
        print(f"\nERROR: 数据库操作失败 → {e}")
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            print("\n数据库连接已关闭。")


if __name__ == "__main__":
    main()