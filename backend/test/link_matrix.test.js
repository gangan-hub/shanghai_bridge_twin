/**
 * 单元测试：链接矩阵 CSV 读取及节点连线处理逻辑
 * 使用 Node.js 内置 node:test 模块，无需额外依赖
 * 运行方式：node --test test/link_matrix.test.js
 */

import { describe, it } from "node:test";
import assert from "node:assert/strict";
import path from "path";
import fs from "fs";
import { execFile } from "child_process";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
const LINK_MATRIX_CSV = path.join(
  PROJECT_ROOT,
  "ai_models_flow",
  "shanghai_data",
  "generate_acc_shanghai",
  "link_matrix_shanghai.csv"
);

// ========== 核心逻辑函数（从端点中提取，用于独立测试） ==========

/**
 * 解析 CSV 矩阵文本，提取上三角连接边
 * @param {string} csvText - CSV 文件内容
 * @returns {{ edges: Array, matrixShape: number[], totalNodes: number }}
 */
function parseLinkMatrixCSV(csvText) {
  const lines = csvText.trim().split("\n");
  if (lines.length < 2) throw new Error("CSV 数据不足");

  // 跳过表头行
  const matrix = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",");
    if (cols.length < 2) continue;
    // 跳过行索引列（第一个值），解析后续数值
    const values = cols.slice(1).map(Number);
    matrix.push(values);
  }

  const n = matrix.length;
  const m = matrix[0]?.length || 0;
  const edges = [];

  // 遍历上三角 (i < j)，value > 0 则创建边，排除对角线 (i === j)
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < Math.min(m, n); j++) {
      const val = matrix[i][j];
      if (val > 0) {
        edges.push({
          source: i,
          target: j,
          weight: parseFloat(val.toFixed(10)),
        });
      }
    }
  }

  return { edges, matrixShape: [n, m], totalNodes: n };
}

/**
 * 判断给定数值是否应创建连接边
 * @param {number} value - 矩阵中的数值
 * @returns {boolean}
 */
function shouldCreateEdge(value) {
  return value > 0;
}

// ========== 测试用例 ==========

describe("数值判定逻辑", () => {
  it("值 > 0 时应创建连接边", () => {
    assert.equal(shouldCreateEdge(0.5), true);
    assert.equal(shouldCreateEdge(1.0), true);
    assert.equal(shouldCreateEdge(0.001), true);
    assert.equal(shouldCreateEdge(0.1152), true);
    assert.equal(shouldCreateEdge(1e-10), true, "极小正数也应创建边");
  });

  it("值 = 0 时不应创建连接边", () => {
    assert.equal(shouldCreateEdge(0), false);
    assert.equal(shouldCreateEdge(0.0), false);
  });

  it("值 < 0 时不应创建连接边", () => {
    assert.equal(shouldCreateEdge(-1), false);
    assert.equal(shouldCreateEdge(-0.5), false);
  });
});

describe("CSV 矩阵解析 - 小矩阵模拟", () => {
  // 构造一个 4×4 的小型测试矩阵 CSV
  const testCSV = [
    ",0,1,2,3",     // 表头
    "0,1.0,0.5,0.0,0.3",  // 行0
    "1,0.5,1.0,0.2,0.0",  // 行1
    "2,0.0,0.2,1.0,0.8",  // 行2
    "3,0.3,0.0,0.8,1.0",  // 行3
  ].join("\n");

  it("应正确解析 4×4 矩阵", () => {
    const result = parseLinkMatrixCSV(testCSV);
    assert.deepEqual(result.matrixShape, [4, 4]);
    assert.equal(result.totalNodes, 4);
  });

  it("应只提取上三角边，排除对角线", () => {
    const result = parseLinkMatrixCSV(testCSV);
    const { edges } = result;

    // 验证不包含自连接（对角线）
    const selfLoops = edges.filter((e) => e.source === e.target);
    assert.equal(selfLoops.length, 0, "不应包含自连接边");

    // 验证所有边都是 source < target（上三角）
    for (const edge of edges) {
      assert.ok(edge.source < edge.target, `边 ${edge.source}-${edge.target} 不满足上三角条件`);
    }
  });

  it("应正确提取所有有效连接边", () => {
    const result = parseLinkMatrixCSV(testCSV);
    const { edges } = result;

    // 预期上三角非零值：
    // [0,1]=0.5, [0,3]=0.3, [1,2]=0.2, [2,3]=0.8
    // [0,2]=0.0 → 不创建
    // [1,3]=0.0 → 不创建
    const expected = [
      { source: 0, target: 1, weight: 0.5 },
      { source: 0, target: 3, weight: 0.3 },
      { source: 1, target: 2, weight: 0.2 },
      { source: 2, target: 3, weight: 0.8 },
    ];

    assert.equal(edges.length, expected.length, `边数应为 ${expected.length}`);
    for (const exp of expected) {
      const found = edges.find((e) => e.source === exp.source && e.target === exp.target);
      assert.ok(found, `应存在边 ${exp.source}-${exp.target}`);
      assert.equal(found.weight, exp.weight, `边 ${exp.source}-${exp.target} 权重应为 ${exp.weight}`);
    }
  });

  it("值为 0 的节点对应创建连接", () => {
    const result = parseLinkMatrixCSV(testCSV);
    const { edges } = result;

    // [0,2] = 0.0 → 不应有边
    const edge02 = edges.find((e) => e.source === 0 && e.target === 2);
    assert.equal(edge02, undefined, "节点 0-2 之间不应有连接（值为 0）");

    // [1,3] = 0.0 → 不应有边
    const edge13 = edges.find((e) => e.source === 1 && e.target === 3);
    assert.equal(edge13, undefined, "节点 1-3 之间不应有连接（值为 0）");
  });
});

describe("CSV 矩阵解析 - 边界情况", () => {
  it("全零矩阵应返回空边列表", () => {
    const csv = [
      ",0,1,2",
      "0,0.0,0.0,0.0",
      "1,0.0,0.0,0.0",
      "2,0.0,0.0,0.0",
    ].join("\n");
    const result = parseLinkMatrixCSV(csv);
    assert.equal(result.edges.length, 0);
    assert.equal(result.totalNodes, 3);
  });

  it("仅有对角线的矩阵应返回空边列表", () => {
    const csv = [
      ",0,1,2",
      "0,1.0,0.0,0.0",
      "1,0.0,1.0,0.0",
      "2,0.0,0.0,1.0",
    ].join("\n");
    const result = parseLinkMatrixCSV(csv);
    assert.equal(result.edges.length, 0, "对角线值不应生成连接边");
  });

  it("完全连接矩阵应返回所有上三角边", () => {
    const csv = [
      ",0,1,2",
      "0,1.0,0.5,0.3",
      "1,0.5,1.0,0.7",
      "2,0.3,0.7,1.0",
    ].join("\n");
    const result = parseLinkMatrixCSV(csv);
    // 上三角：[0,1], [0,2], [1,2] = 3 条边
    assert.equal(result.edges.length, 3);
  });
});

describe("实际 CSV 文件验证", () => {
  it("link_matrix_shanghai.csv 文件应存在", () => {
    assert.ok(fs.existsSync(LINK_MATRIX_CSV), `文件不存在: ${LINK_MATRIX_CSV}`);
  });

  it("实际文件应可正确解析并输出统计信息", async () => {
    // 读取文件内容
    const csvText = fs.readFileSync(LINK_MATRIX_CSV, "utf-8");
    const result = parseLinkMatrixCSV(csvText);

    console.log("\n========== 节点连接统计信息 ==========");
    console.log(`总节点数: ${result.totalNodes}`);
    console.log(`矩阵形状: ${result.matrixShape.join("×")}`);
    console.log(`有效连接边总数: ${result.edges.length}`);

    // 基本校验
    assert.equal(result.totalNodes, 332, "应有 332 个节点");
    assert.deepEqual(result.matrixShape, [332, 332], "矩阵应为 332×332");
    assert.ok(result.edges.length > 0, "应存在有效连接边");

    // 验证所有边权重 > 0
    for (const edge of result.edges) {
      assert.ok(edge.weight > 0, `边 ${edge.source}-${edge.target} 权重应 > 0，实际: ${edge.weight}`);
    }

    // 验证所有边满足 source < target（上三角去重）
    for (const edge of result.edges) {
      assert.ok(edge.source < edge.target, `边 ${edge.source}-${edge.target} 不满足上三角`);
    }

    // 验证权重范围 0~1
    for (const edge of result.edges) {
      assert.ok(edge.weight > 0 && edge.weight <= 1.0, `边 ${edge.source}-${edge.target} 权重超出 (0,1] 范围: ${edge.weight}`);
    }

    // 输出前 20 条连接边
    console.log("\n前 20 条连接边:");
    for (let i = 0; i < Math.min(20, result.edges.length); i++) {
      const e = result.edges[i];
      console.log(`  节点 ${e.source} <-> 节点 ${e.target}  权重: ${e.weight}`);
    }

    console.log("\n=========================================\n");
  });

  it("矩阵应为对称矩阵（验证对称性）", () => {
    const csvText = fs.readFileSync(LINK_MATRIX_CSV, "utf-8");
    const lines = csvText.trim().split("\n");
    const matrix = [];
    for (let i = 1; i < lines.length; i++) {
      const cols = lines[i].split(",");
      if (cols.length < 2) continue;
      matrix.push(cols.slice(1).map(Number));
    }

    const n = matrix.length;
    let asymCount = 0;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        if (Math.abs(matrix[i][j] - matrix[j][i]) > 1e-8) {
          asymCount++;
        }
      }
    }
    console.log(`对称性检查：非对称元素对数 = ${asymCount}`);
    assert.equal(asymCount, 0, "矩阵应为对称矩阵");
  });
});

describe("Python 脚本集成测试", () => {
  it("Python 端点内嵌脚本应正确执行并返回有效 JSON", async () => {
    const csvPathEscaped = LINK_MATRIX_CSV.replace(/\\/g, "\\\\");

    const pySrc = `
import sys, json, csv, os

csv_path = r"${csvPathEscaped}"

if not os.path.exists(csv_path):
    sys.stderr.write(f"ERROR: file not found: {csv_path}\\n")
    sys.exit(1)

try:
    matrix = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) < 2:
                continue
            values = [float(v) for v in row[1:]]
            matrix.append(values)

    n = len(matrix)
    m = len(matrix[0]) if n > 0 else 0

    edges = []
    for i in range(n):
        for j in range(i + 1, min(m, n)):
            val = matrix[i][j]
            if val > 0:
                edges.append({"source": i, "target": j, "weight": round(val, 6)})

    result = {
        "edges": edges,
        "edgeCount": len(edges),
        "matrixShape": [n, m],
        "totalNodes": n,
    }
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))

except Exception as e:
    sys.stderr.write(f"ERROR: {e}\\n")
    sys.exit(1)
`;

    const stdout = await new Promise((resolve, reject) => {
      execFile(
        "C:\\Program Files\\Python312\\python.exe",
        ["-c", pySrc],
        { maxBuffer: 1024 * 1024 * 20, timeout: 120000 },
        (err, stdout, stderr) => {
          if (err) {
            reject(new Error(`Python 执行失败: ${stderr || err.message}`));
            return;
          }
          resolve(stdout.trim());
        }
      );
    });

    const data = JSON.parse(stdout);

    console.log("\n========== Python 脚本集成测试 ==========");
    console.log(`总节点数: ${data.totalNodes}`);
    console.log(`矩阵形状: ${data.matrixShape.join("×")}`);
    console.log(`有效连接边总数: ${data.edgeCount}`);
    console.log("===========================================\n");

    assert.equal(data.totalNodes, 332);
    assert.deepEqual(data.matrixShape, [332, 332]);
    assert.ok(data.edgeCount > 0, "Python 脚本应返回有效边数");
    assert.equal(data.edges.length, data.edgeCount, "边列表长度应等于 edgeCount");
  });
});

// ========== file_reader_service.py 统一文件读取测试 ==========

const SHANGHAI_XLSX = path.join(
  PROJECT_ROOT, "ai_models_flow", "shanghai_data", "shanghaidata_x.xlsx"
);
const FILE_READER_SCRIPT = path.join(
  __dirname, "..", "src", "file_reader_service.py"
);

/**
 * 运行 file_reader_service.py 并返回解析后的 JSON
 */
async function runFileReader(args) {
  const stdout = await new Promise((resolve, reject) => {
    execFile(
      "C:\\Program Files\\Python312\\python.exe",
      [FILE_READER_SCRIPT, ...args],
      { maxBuffer: 100 * 1024 * 1024, timeout: 120000 },
      (err, stdout, stderr) => {
        if (err) reject(new Error(`Python 执行失败: ${stderr || err.message}`));
        else resolve(stdout.trim());
      }
    );
  });
  return JSON.parse(stdout);
}

describe("file_reader_service.py - 统一文件读取服务", () => {
  it("脚本文件应存在", () => {
    assert.ok(fs.existsSync(FILE_READER_SCRIPT), `脚本不存在: ${FILE_READER_SCRIPT}`);
  });

  it("mode=csv 应正确读取链接矩阵并返回边数据", async () => {
    const data = await runFileReader(["--mode", "csv", "--csv", LINK_MATRIX_CSV]);

    assert.ok(data.csv, "应包含 csv 字段");
    assert.equal(data.csv.success, true, "csv 读取应成功");
    assert.equal(data.csv.edgeCount, 1104, "应有 1104 条无向边");
    assert.deepEqual(data.csv.matrixShape, [332, 332], "矩阵应为 332×332");
    assert.equal(data.csv.edges.length, 1104, "边列表长度应为 1104");

    // 验证所有边满足 source < target
    for (const edge of data.csv.edges) {
      assert.ok(edge.source < edge.target, `边 ${edge.source}-${edge.target} 不满足上三角`);
    }

    console.log("\n========== file_reader_service mode=csv ==========");
    console.log(`边数: ${data.csv.edgeCount}, 矩阵: ${data.csv.matrixShape.join("×")}`);
    console.log(`耗时: ${data.csv.elapsed_ms}ms`);
    console.log("====================================================\n");
  });

  it("mode=xlsx 应正确读取节点坐标并包含 WGS84 字段", async () => {
    const data = await runFileReader(["--mode", "xlsx", "--xlsx", SHANGHAI_XLSX]);

    assert.ok(data.xlsx, "应包含 xlsx 字段");
    assert.equal(data.xlsx.success, true, "xlsx 读取应成功");
    assert.equal(data.xlsx.nodeCount, 332, "应有 332 个节点");
    assert.ok(Array.isArray(data.xlsx.nodes), "nodes 应为数组");
    assert.equal(data.xlsx.nodes.length, 332, "nodes 长度应为 332");

    // 验证每个节点包含必要字段
    const first = data.xlsx.nodes[0];
    assert.ok("node" in first, "应包含 node 字段");
    assert.ok("node_0base" in first, "应包含 node_0base 字段");
    assert.ok("name" in first, "应包含 name 字段");
    assert.ok("wgs84_lng" in first, "应包含 wgs84_lng 字段");
    assert.ok("wgs84_lat" in first, "应包含 wgs84_lat 字段");
    assert.ok(Number.isFinite(first.wgs84_lng), "wgs84_lng 应为有限数值");
    assert.ok(Number.isFinite(first.wgs84_lat), "wgs84_lat 应为有限数值");

    // 验证 node_0base 范围 0-331
    assert.equal(first.node_0base, 0, "第一个节点 node_0base 应为 0");
    const last = data.xlsx.nodes[331];
    assert.equal(last.node_0base, 331, "最后一个节点 node_0base 应为 331");

    console.log("\n========== file_reader_service mode=xlsx ==========");
    console.log(`节点数: ${data.xlsx.nodeCount}`);
    console.log(`首节点: node=${first.node}, lng=${first.wgs84_lng}, lat=${first.wgs84_lat}`);
    console.log("=====================================================\n");
  });

  it("mode=all 应同时读取 xlsx 和 csv", async () => {
    const data = await runFileReader([
      "--mode", "all", "--xlsx", SHANGHAI_XLSX, "--csv", LINK_MATRIX_CSV,
    ]);

    assert.ok(data.xlsx, "应包含 xlsx 字段");
    assert.ok(data.csv, "应包含 csv 字段");
    assert.equal(data.xlsx.success, true);
    assert.equal(data.csv.success, true);
    assert.equal(data.xlsx.nodeCount, 332);
    assert.equal(data.csv.edgeCount, 1104);
  });

  it("xlsx 文件不存在时应返回错误但不崩溃", async () => {
    const data = await runFileReader([
      "--mode", "xlsx", "--xlsx", "C:\\nonexistent\\fake.xlsx",
    ]);

    assert.ok(data.xlsx, "应包含 xlsx 字段");
    assert.equal(data.xlsx.success, false, "应标记为失败");
    assert.ok(data.xlsx.error, "应包含错误信息");
    assert.ok(data.xlsx.error.includes("未找到") || data.xlsx.error.includes("不存在"),
      "错误信息应提示文件不存在");
  });

  it("csv 文件不存在时应返回错误但不崩溃", async () => {
    const data = await runFileReader([
      "--mode", "csv", "--csv", "C:\\nonexistent\\fake.csv",
    ]);

    assert.ok(data.csv, "应包含 csv 字段");
    assert.equal(data.csv.success, false, "应标记为失败");
    assert.ok(data.csv.error, "应包含错误信息");
    assert.ok(data.csv.error.includes("未找到") || data.csv.error.includes("不存在"),
      "错误信息应提示文件不存在");
  });

  it("mode=all 且两个文件都不存在时应返回两个错误", async () => {
    const data = await runFileReader([
      "--mode", "all",
      "--xlsx", "C:\\nonexistent\\fake.xlsx",
      "--csv", "C:\\nonexistent\\fake.csv",
    ]);

    assert.ok(data.xlsx, "应包含 xlsx 字段");
    assert.ok(data.csv, "应包含 csv 字段");
    assert.equal(data.xlsx.success, false);
    assert.equal(data.csv.success, false);
    assert.ok(Array.isArray(data.errors), "errors 应为数组");
    assert.equal(data.errors.length, 2, "应有 2 个错误");
  });

  it("csv 格式错误（非法数值）时应返回错误", async () => {
    // 创建一个临时 CSV 文件包含非法数据
    const tmpPath = path.join(__dirname, "bad_format_test.csv");
    fs.writeFileSync(tmpPath, [
      ",0,1,2",
      "0,1.0,not_a_number,0.5",
      "1,not_a_number,1.0,0.3",
      "2,0.5,0.3,1.0",
    ].join("\n"));

    try {
      const data = await runFileReader(["--mode", "csv", "--csv", tmpPath]);
      assert.ok(data.csv, "应包含 csv 字段");
      assert.equal(data.csv.success, false, "格式错误应标记为失败");
      assert.ok(data.csv.error, "应包含错误信息");
    } finally {
      // 清理临时文件
      if (fs.existsSync(tmpPath)) fs.unlinkSync(tmpPath);
    }
  });
});
