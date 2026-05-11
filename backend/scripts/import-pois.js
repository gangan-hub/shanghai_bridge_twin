import fs from "node:fs";
import path from "node:path";
import pg from "pg";
import dotenv from "dotenv";

dotenv.config();

async function run() {
  const sqlPath = path.resolve(process.cwd(), "..", "update_pois.sql");
  if (!fs.existsSync(sqlPath)) {
    console.error(`SQL file not found: ${sqlPath}`);
    return;
  }

  const pool = new pg.Pool({
    host: process.env.DB_HOST,
    port: Number(process.env.DB_PORT || 5432),
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
  });

  try {
    const sql = fs.readFileSync(sqlPath, "utf8");
    console.log("Starting to import POIs...");
    await pool.query(sql);
    console.log("Successfully integrated POI data into the database.");
  } catch (e) {
    console.error("Error integrating data:", e.message);
  } finally {
    await pool.end();
  }
}

run();
