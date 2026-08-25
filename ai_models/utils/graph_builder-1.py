import pandas as pd
import numpy as np
import os
import networkx as nx
import matplotlib.pyplot as plt
from sklearn.neighbors import kneighbors_graph

# ----------------- 1. 路径自动定位 -----------------
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(os.path.dirname(current_dir), 'data', '上海市桥梁POI数据.xlsx')

if not os.path.exists(file_path):
    file_path = '上海市桥梁POI数据.xlsx'

# ----------------- 2. 读取文件与精准坐标提取 -----------------
print(f"正在读取 Excel 数据文件: {file_path}")
try:
    df = pd.read_excel(file_path)

    # ⚠️ 核心修复：根据终端报错，将列名改为实际的 'x' 和 'y'
    lng_col = 'x'
    lat_col = 'y'

    # 提取真实的坐标数据
    coords = df[[lng_col, lat_col]].values
    print(f"✅ 成功提取 {len(coords)} 个桥梁节点的真实坐标！")
    print(f"坐标示例 -> 经度(x): {coords[0, 0]:.4f}, 纬度(y): {coords[0, 1]:.4f}")

except KeyError:
    print(f"❌ 提取失败！在 Excel 中找不到 '{lng_col}' 或 '{lat_col}' 列。")
    print(f"当前 Excel 包含的实际列名有: {list(df.columns)}")
    import sys

    sys.exit()  # 使用 sys.exit() 确保在 IPython/PyCharm 控制台中也能真正打断程序
except ImportError:
    print("❌ 缺少读取 Excel 的库！请在终端运行: pip install openpyxl")
    import sys

    sys.exit()
except Exception as e:
    print(f"❌ 读取失败！错误原因: {e}")
    import sys

    sys.exit()


# ----------------- 3. 构建 KNN 拓扑图 -----------------
def build_knn_graph(node_features, k=5):
    """根据真实的物理坐标构建 KNN 邻接矩阵并转为无向图"""
    knn_sparse = kneighbors_graph(node_features, n_neighbors=k, mode='connectivity', include_self=False)
    knn_matrix = np.maximum(knn_sparse.toarray(), knn_sparse.toarray().T)
    np.fill_diagonal(knn_matrix, 1.0)
    return knn_matrix


K_VALUE = 5
print(f"正在构建 KNN 拓扑图 (K={K_VALUE})...")
knn_adj = build_knn_graph(coords, k=K_VALUE)

# ----------------- 4. 最终结果输出 -----------------
np.save('../data/knn_adj.npy', knn_adj)
print(f"✅ 已保存模型特征矩阵: knn_adj.npy (形状: {knn_adj.shape})")

# B. 输出 .png 图片格式 (写毕业论文贴图用)
print("正在生成网络拓扑结构可视化图片...")

# ⚠️ 修复圆圈问题：复制一份矩阵，把对角线清零，专门用来画图
vis_matrix = knn_adj.copy()
np.fill_diagonal(vis_matrix, 0.0)

# 使用清除了自环的矩阵来画图，这样就只有节点之间的直线了！
G = nx.from_numpy_array(vis_matrix)
pos = {i: (coords[i, 0], coords[i, 1]) for i in range(len(coords))}

plt.figure(figsize=(10, 8))
nx.draw(G, pos, node_size=25, node_color='#1f77b4', edge_color='#cccccc', alpha=0.8, with_labels=False)

plt.title(f"Shanghai Bridge KNN Network Topology (K={K_VALUE})", fontsize=14)
plt.axis('equal')
plt.tight_layout()
plt.savefig('graph_visualization.png', dpi=300, bbox_inches='tight')
print("✅ 已保存高清拓扑图片: graph_visualization.png")