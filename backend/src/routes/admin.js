import express from "express";
import { authRequired } from "../auth.js";
import { exec } from "child_process";
import path from "path";
import fs from "fs";
import { query } from "../db.js";

const router = express.Router();

// 触发爬虫数据同步
router.post("/sync-pois", authRequired, async (req, res) => {
  if (req.user.role !== "admin") {
    return res.status(403).json({ message: "Only admins can sync data" });
  }

  const crawlerPath = path.resolve(process.cwd(), "..", "crawler.py");
  const importScriptPath = path.resolve(process.cwd(), "scripts", "import-pois.js");

  console.log("Starting data sync...");

  // 执行 Python 爬虫
  exec(`python "${crawlerPath}"`, (err, stdout, stderr) => {
    if (err) {
      console.error("Crawler error:", err);
      return res.status(500).json({ message: "Crawler failed", detail: stderr });
    }
    
    console.log("Crawler finished, starting import...");

    // 执行导入脚本
    exec(`node "${importScriptPath}"`, (err2, stdout2, stderr2) => {
      if (err2) {
        console.error("Import error:", err2);
        return res.status(500).json({ message: "Import failed", detail: stderr2 });
      }
      
      console.log("Data sync completed successfully");
      return res.json({ message: "Sync completed", log: stdout2 });
    });
  });
});

// 绑定模型到桥梁
router.put("/bridges/:id/model", authRequired, async (req, res) => {
  if (req.user.role !== "admin") {
    return res.status(403).json({ message: "Only admins can update models" });
  }

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
