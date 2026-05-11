import express from "express";
import { exec } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const router = express.Router();

router.post('/start-shanghai', (req, res) => {
    const { node = "0", typ = 2 } = req.body;

    const scriptPath = path.resolve(__dirname, '../../../ai_models_jam/spread_core_shanghai.py'); 
    const jsonPath = path.resolve(__dirname, '../../../ai_models_jam/data_shanghai/output/spread_sequence.json');
    const pythonExe = path.resolve(__dirname, '../../../venv/Scripts/python.exe'); 

    const cmd = `"${pythonExe}" "${scriptPath}" "${node}" ${typ}`;
    console.log("-----------------------------------------");
    console.log("🚀 执行 Python 指令:", cmd);

    // 关键配置：设置工作目录为 Python 目录，并强制设置 Python 输出编码为 utf-8
    const options = {
        cwd: path.resolve(__dirname, '../../../ai_models_jam'),
        env: {
            ...process.env,
            PYTHONIOENCODING: "utf-8"
        }
    };

    exec(cmd, options, (error, stdout, stderr) => {
        if (stdout) console.log("【Python 输出】:\n", stdout);
        
        if (error) {
            console.error("❌ Python 执行失败:\n", stderr || error.message);
            return res.status(500).json({ 
                message: 'Python 脚本执行失败', 
                error: stderr || error.message 
            });
        }

        // 检查生成的 JSON 文件
        if (!fs.existsSync(jsonPath)) {
            console.error("❌ 未找到生成的 JSON 文件:", jsonPath);
            return res.status(500).json({ message: '模型已运行，但未生成 spread_sequence.json 文件' });
        }

        fs.readFile(jsonPath, 'utf8', (err, data) => {
            if (err) {
                console.error("❌ 读取 JSON 文件出错:", err);
                return res.status(500).json({ message: '读取生成的 JSON 结果文件失败' });
            }

            try {
                const parsedData = JSON.parse(data);
                console.log("✅ 成功解析 JSON 并返回前端！");
                res.json(parsedData);
            } catch (parseErr) {
                console.error("❌ JSON 解析格式错误");
                res.status(500).json({ message: '生成的 JSON 文件内容格式不合法' });
            }
        });
    });
});

export default router;