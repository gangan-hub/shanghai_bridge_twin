import fs from "fs";
import { query } from "./src/db.js";

// 1. 总数
const countResult = await query(`SELECT COUNT(*) as total FROM bridges`);
console.log(`\n=== 桥梁总记录数: ${countResult.rows[0].total} ===\n`);

// 2. 前20条数据样本
const sample = await query(`SELECT id, code, name, bridge_type, typecode, lon, lat, node_0base, display_idx FROM bridges ORDER BY id LIMIT 20`);
fs.writeFileSync("db_sample.txt", JSON.stringify(sample.rows, null, 2), "utf-8");
console.log("前20条数据已写入 db_sample.txt");

// 3. 有多少条有经纬度
const withCoords = await query(`SELECT COUNT(*) as cnt FROM bridges WHERE lon IS NOT NULL AND lat IS NOT NULL`);
console.log(`\n有经纬度的记录: ${withCoords.rows[0].cnt}`);

// 4. 经纬度范围
const coordsRange = await query(`SELECT MIN(lon) as min_lon, MAX(lon) as max_lon, MIN(lat) as min_lat, MAX(lat) as max_lat FROM bridges WHERE lon IS NOT NULL AND lat IS NOT NULL`);
console.log(`经纬度范围:`, JSON.stringify(coordsRange.rows[0]));

// 5. typecode分布
const typecodeDist = await query(`SELECT typecode, bridge_type, COUNT(*) as cnt FROM bridges WHERE typecode IS NOT NULL GROUP BY typecode, bridge_type ORDER BY typecode`);
console.log(`\nTypecode分布:`);
console.log(JSON.stringify(typecodeDist.rows, null, 2));

// 6. 表结构
const columns = await query(`SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'bridges' ORDER BY ordinal_position`);
fs.writeFileSync("db_columns.txt", JSON.stringify(columns.rows, null, 2), "utf-8");
console.log(`\n表结构已写入 db_columns.txt`);

process.exit(0);
