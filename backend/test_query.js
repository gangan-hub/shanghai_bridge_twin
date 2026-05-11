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
    const res = await pool.query("SELECT code, name FROM bridges WHERE name LIKE '%川杨河桥%' OR name LIKE '%耀龙路桥%'");
    console.log(JSON.stringify(res.rows, null, 2));
  } catch (e) {
    console.error(e);
  } finally {
    await pool.end();
  }
}

run();
