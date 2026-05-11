import express from "express";
import { exec } from "child_process";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";
import { authRequired } from "../auth.js";
import axios from "axios";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const router = express.Router();

const PROJECT_ROOT = path.resolve(__dirname, "..", "..", "..");
const INFERENCE_PY = path.join(PROJECT_ROOT, "ai_models_flow", "inference.py");
const LINK_CSV = path.join(
  PROJECT_ROOT,
  "ai_models_flow",
  "shanghai_data",
  "generate_acc_shanghai",
  "link_matrix_shanghai.csv"
);

/* ===============================
 * 自动查找可用的带 torch 的 Python 解释器
 * =============================== */
function resolvePythonBin() {
  const candidates = [
    // 1. 用户系统 Python312 (已确认安装 torch)
    "C:\\Program Files\\Python312\\python.exe",
    // 2. 项目 .venv (torch 可能在此)
    path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe"),
    // 3. 常见 conda base
    "C:\\Users\\Administrator\\anaconda3\\python.exe",
    "C:\\ProgramData\\anaconda3\\python.exe",
    // 4. 系统默认
    "python",
    "python3",
    "py -3",
  ];
  return candidates[0];
}
const PYTHON_BIN = resolvePythonBin();

/* ===============================
 * 接口 1: 查询空间拓扑连线 (Cesium 加载)
 * 直接读取 link_matrix_shanghai.csv（邻接矩阵）：
 * - 第一行是列头（空 + 0..N-1）
 * - 每行第一个字段是行索引，后续字段是对应列的权重
 * - 上三角去重 i < j，权重 > 0 即为一条连线
 * - source/target 为 0-based 整数，对应 bridges 数组下标
 * 纯 Node.js 解析，无 Python 依赖；CSV 静态不变，首次解析后缓存。
 * =============================== */
let cachedTopology = null;
function loadLinkMatrix() {
  if (cachedTopology) return cachedTopology;
  if (!fs.existsSync(LINK_CSV)) {
    throw new Error("Link CSV file not found at " + LINK_CSV);
  }
  const csvText = fs.readFileSync(LINK_CSV, "utf-8");
  const lines = csvText.split(/\r?\n/).filter((l) => l.trim() !== "");
  if (lines.length === 0) throw new Error("Link CSV is empty: " + LINK_CSV);
  const headerCols = lines[0].split(",");
  const num_nodes = headerCols.length - 1; // 首列名称为空
  const links = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(",");
    if (parts.length < 2) continue;
    const src = parseInt(parts[0], 10);
    if (!Number.isFinite(src)) continue;
    for (let j = src + 1; j < num_nodes; j++) {
      const raw = parts[j + 1]; // 列 j 的值在 parts[j+1]（parts[0] 是行索引）
      if (raw == null || raw === "") continue;
      const w = parseFloat(raw);
      if (Number.isFinite(w) && w > 0) {
        links.push({ source: src, target: j, weight: w });
      }
    }
  }
  cachedTopology = {
    csv_path: LINK_CSV,
    threshold: "weight > 0",
    num_nodes,
    num_links: links.length,
    links,
  };
  return cachedTopology;
}

router.get("/topology", authRequired, async (req, res) => {
  try {
    const data = loadLinkMatrix();
    return res.json({
      csv_path:  data.csv_path,
      threshold: data.threshold,
      num_nodes: data.num_nodes,
      num_links: data.num_links,
      links:     data.links,
    });
  } catch (e) {
    console.error("[gnn topology] error:", e);
    return res.status(500).json({ error: e.message || String(e) });
  }
});

/* ===============================
 * 接口 2: 运行 V-STGRN 模型实时推演
 * 直接调用 ai_models_flow/inference.py (weekday + hour)
 * =============================== */
router.post("/inference_real", authRequired, async (req, res) => {
  const { weekday = 1, hour = 12 } = req.body;
  const w = Math.max(1, Math.min(7, parseInt(weekday, 10) || 1));
  const h = Math.max(0, Math.min(23, parseInt(hour, 10) || 12));

  if (!fs.existsSync(INFERENCE_PY)) {
    return res.status(503).json({ error: "inference.py not found at " + INFERENCE_PY });
  }
  if (!fs.existsSync(PYTHON_BIN)) {
    return res.status(503).json({ error: "Python venv not found at " + PYTHON_BIN });
  }

  const cmd = `"${PYTHON_BIN}" "${INFERENCE_PY}" ${w} ${h}`;
  const cwd = path.dirname(INFERENCE_PY);

  console.log("[GNN] Run:", cmd);
  console.log("[GNN] CWD:", cwd);

  exec(
    cmd,
    {
      cwd,
      maxBuffer: 200 * 1024 * 1024,
      timeout: 600 * 1000,
      windowsHide: true,
      // ===== 强制 UTF-8 输出 (Windows cmd/PowerShell 默认 GBK 导致 Python 报 UnicodeEncodeError) =====
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
        PYTHONUTF8: "1",
        OPENBLAS_NUM_THREADS: "1",
      },
    },
    (error, stdout, stderr) => {
      if (stderr && stderr.trim()) {
        console.log("[GNN Python log]:\n", stderr.slice(-800));
      }
      if (error) {
        console.error("[GNN] exec error:", error.message);
        // 解析可能已经部分输出了 JSON
        const jsonStart = stdout.indexOf("{");
        const jsonEnd = stdout.lastIndexOf("}");
        if (jsonStart >= 0 && jsonEnd > jsonStart) {
          try {
            const data = JSON.parse(stdout.slice(jsonStart, jsonEnd + 1));
            if (data.error) {
              return res.status(400).json({ error: data.error });
            }
          } catch (_) {}
        }
        return res.status(500).json({
          error: "推演脚本执行失败: " + error.message,
          stderr: stderr ? stderr.slice(-1000) : null,
        });
      }
      try {
        const jsonStart = stdout.indexOf("{");
        const jsonEnd = stdout.lastIndexOf("}");
        if (jsonStart < 0 || jsonEnd <= jsonStart) {
          return res.status(500).json({ error: "脚本未返回 JSON", stdout: stdout.slice(-500) });
        }
        const data = JSON.parse(stdout.slice(jsonStart, jsonEnd + 1));
        if (data.error) {
          return res.status(400).json({ error: data.error });
        }
        return res.json(data);
      } catch (e) {
        return res.status(500).json({ error: "解析 JSON 失败: " + e.message, stdout: stdout.slice(-1000) });
      }
    }
  );
});

/* ===============================
 * 原有接口: FastAPI (旧) 兼容保留
 * =============================== */
router.post("/inference", authRequired, async (req, res) => {
  const { bridgeCode } = req.body;
  try {
    const response = await axios.post("http://127.0.0.1:8000/api/simulate", {
      bridgeCode: bridgeCode,
    });
    return res.json(response.data);
  } catch (error) {
    console.error("FastAPI connection error:", error.message);
    return res.status(503).json({
      message: "AI 推演服务不可用，请确保 FastAPI 服务已启动 (python ai_models/api_server.py)",
      detail: error.message,
    });
  }
});

export default router;
