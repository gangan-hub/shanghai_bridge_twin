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
    console.log("Cleaning up duplicate Yangpu Bridge records...");
    
    // 找出所有叫“杨浦大桥”的记录，保留 ID 最小的一个，删除其他的
    const res = await pool.query(`
      DELETE FROM bridges 
      WHERE name LIKE '%杨浦大桥%' 
      AND id NOT IN (
        SELECT MIN(id) 
        FROM bridges 
        WHERE name LIKE '%杨浦大桥%'
      )
    `);
    
    console.log(`Deleted ${res.rowCount} duplicate Yangpu Bridge records.`);
    
    const countRes = await pool.query("SELECT COUNT(*) FROM bridges WHERE name LIKE '%杨浦大桥%'");
    console.log(`Remaining Yangpu Bridge records: ${countRes.rows[0].count}`);
  } catch (e) {
    console.error("Cleanup failed:", e.message);
  } finally {
    await pool.end();
  }
}

run();
