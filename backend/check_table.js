import pg from "pg";
const pool = new pg.Pool({host:"127.0.0.1",port:5432,database:"bridge_twin",user:"postgres",password:"123456"});
const {rows} = await pool.query(`SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='bridges' ORDER BY ordinal_position`);
console.log(JSON.stringify(rows,null,2));
pool.end();
