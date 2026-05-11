-- 无 PostGIS 的降级版本：用 lon/lat 字段替代 geography(point)

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'visitor')),
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bridges (
  id SERIAL PRIMARY KEY,
  code VARCHAR(50) UNIQUE NOT NULL,
  name VARCHAR(200) NOT NULL,
  district VARCHAR(100),
  bridge_type VARCHAR(100),
  span_m NUMERIC(10,2),
  built_year INT,
  design_unit VARCHAR(200),
  description TEXT,
  photos JSONB DEFAULT '[]'::jsonb,
  model_path TEXT,
  -- 可选：用于“点选校准”的 WGS84 坐标（优先用于定位）
  wgs_lon NUMERIC(9,6),
  wgs_lat NUMERIC(9,6),
  lon NUMERIC(9,6) NOT NULL,
  lat NUMERIC(9,6) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bridges_lon_lat ON bridges (lon, lat);

