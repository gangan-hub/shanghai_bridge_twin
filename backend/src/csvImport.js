import fs from "fs";
import path from "path";
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

const CACHE_FILE = path.join(
  PROJECT_ROOT,
  "ai_models_flow",
  "shanghai_data",
  "generate_acc_shanghai",
  "link_matrix_cache.json"
);

/**
 * 读取 link_matrix_shanghai.csv，解析邻接矩阵，提取边列表，缓存为 JSON。
 * 返回 { edgeCount, totalNodes, matrixShape, cachePath, csvMtime }
 */
export async function importCsvMatrix() {
  if (!fs.existsSync(LINK_MATRIX_CSV)) {
    throw new Error(`CSV 文件不存在: ${LINK_MATRIX_CSV}`);
  }

  const csvMtime = new Date(fs.statSync(LINK_MATRIX_CSV).mtime).toISOString();
  const raw = fs.readFileSync(LINK_MATRIX_CSV, "utf-8");
  const lines = raw.split(/\r?\n/).filter((l) => l.trim().length > 0);

  if (lines.length < 2) {
    throw new Error("CSV 文件为空或格式不正确");
  }

  // 第一行是列头: ,0,1,2,...,331
  // 后续每行: 行索引,值0,值1,...,值N
  const matrix = [];
  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(",");
    if (parts.length < 2) continue;
    // 跳过第一列（行索引），取后续数值
    const values = parts.slice(1).map(Number);
    matrix.push(values);
  }

  const n = matrix.length;
  if (n === 0) {
    throw new Error("解析后矩阵为空");
  }
  const m = matrix[0].length;

  // 遍历上三角（i < j），提取 value > 0 的边，排除对角线
  const edges = [];
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < Math.min(m, n); j++) {
      const val = matrix[i][j];
      if (val > 0) {
        edges.push({
          source: i,
          target: j,
          weight: Math.round(val * 1e6) / 1e6,
        });
      }
    }
  }

  // 写入缓存 JSON
  const cacheData = {
    edges,
    edgeCount: edges.length,
    matrixShape: [n, m],
    totalNodes: n,
    csvMtime,
    cachedAt: new Date().toISOString(),
  };
  fs.writeFileSync(CACHE_FILE, JSON.stringify(cacheData, null, 2), "utf-8");

  console.log(
    `[csvImport] parsed ${n}x${m} matrix, ${edges.length} edges, cache: ${CACHE_FILE}`
  );

  return {
    edgeCount: edges.length,
    totalNodes: n,
    matrixShape: [n, m],
    cachePath: CACHE_FILE,
    csvMtime,
  };
}
