import express from "express";
import { authRequired } from "../auth.js";
import { exec } from "child_process";
import path from "path";
import fs from "fs";
import { query } from "../db.js";

import { importExcelData } from "../excelImport.js";

const router = express.Router();

// 触发 Excel 数据同步
router.post("/sync-pois", authRequired, async (req, res) => {
  if (req.user.role !== "admin") {
    return res.status(403).json({ message: "Only admins can sync data" });
  }

  console.log("Starting Excel data sync...");

  try {
    const result = await importExcelData();
    return res.json({ message: "Sync completed from Excel", count: result.count });
  } catch (error) {
    console.error("Sync error:", error);
    return res.status(500).json({ message: "Sync failed", detail: error.message });
  }
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
