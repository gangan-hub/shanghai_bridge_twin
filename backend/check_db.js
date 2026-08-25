import pg from "pg";
import dotenv from "dotenv";

dotenv.config();

async function check() {
  const pool = new pg.Pool({
    host: process.env.DB_HOST,
    port: Number(process.env.DB_PORT || 5432),
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
  });

  try {
    const res = await pool.query("SELECT COUNT(*) FROM bridges");
    console.log("TOTAL_COUNT:" + res.rows[0].count);
    const sample = await pool.query("SELECT * FROM bridges LIMIT 5");
    console.log("SAMPLES:");
    sample.rows.forEach(r => console.log(`- ${r.code}: ${r.name} (${r.wgs_lon}, ${r.wgs_lat})`));
  } catch (e) {
    console.error("Database check failed:", e.message);
  } finally {
    await pool.end();
  }
}

check();
