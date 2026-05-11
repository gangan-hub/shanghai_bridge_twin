import fs from "node:fs";
import path from "node:path";
import pg from "pg";
import dotenv from "dotenv";

dotenv.config();

function requireEnv(name) {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env: ${name}`);
  return v;
}

const DB_HOST = requireEnv("DB_HOST");
const DB_PORT = Number(requireEnv("DB_PORT"));
const DB_NAME = requireEnv("DB_NAME");
const DB_USER = requireEnv("DB_USER");
const DB_PASSWORD = requireEnv("DB_PASSWORD");

const root = path.resolve(process.cwd(), "..");
const schemaPath = path.join(root, "sql", "schema.sql");
const seedPath = path.join(root, "sql", "seed.sql");
const schemaNoPostgisPath = path.join(root, "sql", "schema_nopostgis.sql");
const seedNoPostgisPath = path.join(root, "sql", "seed_nopostgis.sql");

function readSql(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`SQL file not found: ${filePath}`);
  }
  return fs.readFileSync(filePath, "utf8");
}

async function ensureDatabaseExists() {
  const adminPool = new pg.Pool({
    host: DB_HOST,
    port: DB_PORT,
    database: "postgres",
    user: DB_USER,
    password: DB_PASSWORD,
  });

  try {
    const check = await adminPool.query("SELECT 1 FROM pg_database WHERE datname = $1", [DB_NAME]);
    if (check.rowCount > 0) return { created: false };

    // NOTE: 数据库名不能用参数占位符，只能拼接；这里做了基本字符白名单
    if (!/^[a-zA-Z0-9_]+$/.test(DB_NAME)) {
      throw new Error(`Unsafe DB_NAME: ${DB_NAME}. Only [a-zA-Z0-9_] allowed for auto-create.`);
    }

    await adminPool.query(`CREATE DATABASE ${DB_NAME}`);
    return { created: true };
  } finally {
    await adminPool.end();
  }
}

async function runSqlOnTargetDb() {
  const pool = new pg.Pool({
    host: DB_HOST,
    port: DB_PORT,
    database: DB_NAME,
    user: DB_USER,
    password: DB_PASSWORD,
  });

  const schemaSql = readSql(schemaPath);
  const seedSql = readSql(seedPath);
  const schemaNoPostgisSql = readSql(schemaNoPostgisPath);
  const seedNoPostgisSql = readSql(seedNoPostgisPath);

  try {
    await pool.query("BEGIN");
    let usingPostgis = true;
    try {
      await pool.query("CREATE EXTENSION IF NOT EXISTS postgis");
    } catch (_e) {
      usingPostgis = false;
    }

    if (usingPostgis) {
      await pool.query(schemaSql);
      await pool.query(seedSql);
    } else {
      await pool.query(schemaNoPostgisSql);
      await pool.query(seedNoPostgisSql);
    }

    // 兼容升级：为已存在库补齐校准字段（可重复执行）
    await pool.query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS wgs_lon NUMERIC(9,6)");
    await pool.query("ALTER TABLE bridges ADD COLUMN IF NOT EXISTS wgs_lat NUMERIC(9,6)");
    await pool.query("COMMIT");
    return { usingPostgis };
  } catch (e) {
    try {
      await pool.query("ROLLBACK");
    } catch (_e) {
      // ignore
    }
    throw e;
  } finally {
    await pool.end();
  }
}

async function main() {
  const { created } = await ensureDatabaseExists();
  const { usingPostgis } = await runSqlOnTargetDb();
  console.log(
    JSON.stringify(
      {
        ok: true,
        db: DB_NAME,
        createdDatabase: created,
        usingPostgis,
        applied: usingPostgis
          ? ["sql/schema.sql", "sql/seed.sql"]
          : ["sql/schema_nopostgis.sql", "sql/seed_nopostgis.sql"],
      },
      null,
      2
    )
  );
}

main().catch((e) => {
  console.error("db:init failed");
  console.error(e?.message || e);
  process.exit(1);
});

