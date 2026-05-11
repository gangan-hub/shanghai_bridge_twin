import pg from "pg";
import dotenv from "dotenv";
import bcrypt from "bcryptjs";
import readline from "readline";

dotenv.config();

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

async function run() {
  const pool = new pg.Pool({
    host: process.env.DB_HOST,
    port: Number(process.env.DB_PORT || 5432),
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
  });

  rl.question("请输入 admin 的新密码: ", async (newPassword) => {
    try {
      if (!newPassword || newPassword.length < 3) {
        console.error("密码太短，修改取消。");
        process.exit(1);
      }

      const hash = await bcrypt.hash(newPassword, 10);
      const res = await pool.query(
        "UPDATE users SET password_hash = $1 WHERE username = 'admin'",
        [hash]
      );
      
      if (res.rowCount > 0) {
        console.log("\n✅ 密码修改成功！");
        console.log("新密码已立即生效，无需重启服务。");
      } else {
        console.error("\n❌ 未找到 admin 用户，请检查数据库配置。");
      }
    } catch (e) {
      console.error("\n❌ 修改失败:", e.message);
    } finally {
      await pool.end();
      rl.close();
    }
  });
}

run();
