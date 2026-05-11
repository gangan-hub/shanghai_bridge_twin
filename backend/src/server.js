import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import authRouter from "./routes/auth.js";
import bridgesRouter from "./routes/bridges.js";
import modelsRouter from "./routes/models.js";
import adminRouter from "./routes/admin.js";
import { runMigrations } from "./migrate.js";
import { query } from "./db.js";

dotenv.config();

const app = express();
const port = Number(process.env.PORT || 3000);

app.use(cors());
app.use(express.json());
app.use("/models", express.static("models"));

app.get("/health", async (_req, res) => {
  try {
    const r = await query("SELECT COUNT(*)::int AS c FROM bridges");
    return res.json({ ok: true, bridgeCount: r.rows[0]?.c ?? null });
  } catch (e) {
    return res.json({ ok: true, bridgeCount: null, dbError: e?.message || String(e) });
  }
});
app.use("/api/auth", authRouter);
app.use("/api/bridges", bridgesRouter);
app.use("/api/models", modelsRouter);
app.use("/api/admin", adminRouter);

async function start() {
  try {
    await runMigrations();
  } catch (e) {
    console.error("migrate warning:", e?.message || e);
  }
  app.listen(port, () => {
    console.log(`Backend listening on http://localhost:${port}`);
  });
}

start();
