import express from "express";
import { exec } from "child_process";
import path from "path";
import { authRequired } from "../auth.js";

import axios from "axios";

const router = express.Router();

// 获取图网络推演结果 (对接 Python FastAPI 服务)
router.post("/inference", authRequired, async (req, res) => {
  const { bridgeCode } = req.body;
  
  try {
    // 请求 Python FastAPI 服务 (Option 2: API 驱动)
    const response = await axios.post("http://127.0.0.1:8000/api/simulate", {
      bridgeCode: bridgeCode
    });
    
    return res.json(response.data);
  } catch (error) {
    console.error("FastAPI connection error:", error.message);
    
    // 如果 FastAPI 未启动，可以尝试降级到原来的脚本执行模式 (可选)
    return res.status(503).json({ 
      message: "AI 推演服务不可用，请确保 FastAPI 服务已启动 (python ai_models/api_server.py)",
      detail: error.message 
    });
  }
});

export default router;
