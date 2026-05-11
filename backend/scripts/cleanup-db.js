import pg from "pg";
import dotenv from "dotenv";

dotenv.config();

async function run() {
  const pool = new pg.Pool({
    host: process.env.DB_HOST,
    port: Number(process.env.DB_PORT || 5432),
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
  });

  try {
    console.log("Cleaning up non-bridge/tunnel data...");
    // 只有名称或类型中包含“桥”或“隧道”的记录才会被保留
    // 或者基于高德的分类，但我们之前只存储了最终的类型名称
    const res = await pool.query(`
      DELETE FROM bridges 
      WHERE (name NOT LIKE '%桥%' AND name NOT LIKE '%隧道%')
      AND (bridge_type NOT LIKE '%桥%' AND bridge_type NOT LIKE '%隧道%')
    `);
    console.log(`Deleted ${res.rowCount} non-bridge/tunnel records.`);
    
    const countRes = await pool.query("SELECT COUNT(*) FROM bridges");
    console.log(`Remaining records: ${countRes.rows[0].count}`);
  } catch (e) {
    console.error("Cleanup failed:", e.message);
  } finally {
    await pool.end();
  }
}

run();
