import express from "express";
import { authRequired } from "../auth.js";
import { execFile } from "child_process";
import path from "path";
import fs from "fs";
import { query } from "../db.js";

import { getTypecodeMapping } from "../excelImport.js";
import { importCsvMatrix } from "../csvImport.js";

const router = express.Router();

// 触发 Excel 数据同步（调用 Python 脚本）
router.post("/sync-pois", authRequired, async (req, res) => {
  console.log("Starting Excel data sync via Python script...");

  const scriptPath = path.resolve(
    process.cwd(),
    "..",
    "scripts",
    "import_excel_to_bridges.py"
  );

  // 项目本地 Python 依赖目录（psycopg2 等），避免系统 python 未安装时报错
  const localPydeps = path.resolve(process.cwd(), "..", ".pydeps");
  const env = {
    ...process.env,
    PYTHONPATH: localPydeps,
  };

  execFile("python", [scriptPath], { timeout: 60000, env }, (error, stdout, stderr) => {
    // 把 Python 脚本的所有输出都打印出来，方便排错
    console.log("[sync-pois] Python stdout:\n", stdout);
    if (stderr) {
      console.error("[sync-pois] Python stderr:\n", stderr);
    }

    if (error) {
      console.error("[sync-pois] Python script error:", error);
      return res.status(500).json({
        message: "Sync failed",
        detail: error.message,
        stdout,
        stderr,
      });
    }

    // 解析脚本 stdout 中的 JSON 输出
    try {
      const lines = stdout.trim().split("\n");
      const jsonLine = lines[lines.length - 1]; // 最后一行是 JSON
      const result = JSON.parse(jsonLine);

      if (result.status === "ok") {
        return res.json({
          message: "Sync completed from Excel",
          count: result.count,
          coordConverted: result.coord_converted,
          typecodeMap: result.typecodeMap,
        });
      } else {
        return res.status(500).json({
          message: "Sync failed",
          detail: result.message || "Unknown error",
          stdout,
          stderr,
        });
      }
    } catch (parseErr) {
      console.error("Failed to parse Python output:", stdout);
      return res.status(500).json({
        message: "Sync failed",
        detail: "无法解析脚本输出",
        stdout,
        stderr,
      });
    }
  });
});

// 获取 typecode ↔ 桥隧类型 映射
router.get("/typecode-mapping", async (req, res) => {
  try {
    const map = await getTypecodeMapping();
    return res.json(map);
  } catch (error) {
    return res.status(500).json({ message: "Failed to get mapping", detail: error.message });
  }
});

// 触发 CSV 链接矩阵数据同步
router.post("/sync-csv", authRequired, async (req, res) => {
  console.log("Starting CSV link matrix sync...");

  try {
    const result = await importCsvMatrix();
    return res.json({
      message: "CSV 链接矩阵同步完成",
      edgeCount: result.edgeCount,
      totalNodes: result.totalNodes,
      matrixShape: result.matrixShape,
    });
  } catch (error) {
    console.error("CSV sync error:", error);
    return res.status(500).json({ message: "CSV 同步失败", detail: error.message });
  }
});

// 绑定模型到桥梁
router.put("/bridges/:id/model", authRequired, async (req, res) => {
  const { id } = req.params;
  const { modelPath } = req.body;

  try {
    await query(
      "UPDATE bridges SET model_path = $1 WHERE id = $2",
      [modelPath, id]
    );
    return res.json({ message: "Model path updated" });
  } catch (error) {
    return res.status(500).json({ message: "Update failed", detail: error.message });
  }
});

export default router;
