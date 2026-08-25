import pandas as pd
import numpy as np
import os
import networkx as nx
import matplotlib.pyplot as plt
from fastdtw import fastdtw

# ----------------- 1. 自动定位与读取节点数和坐标 -----------------
current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(os.path.dirname(current_dir), 'data', '上海市桥梁POI数据.xlsx')
if not os.path.exists(file_path):
    file_path = '上海市桥梁POI数据.xlsx'

print("正在读取 Excel 获取节点总数与坐标...")
try:
    df = pd.read_excel(file_path)
    num_nodes = len(df)
    # 提取经纬度坐标，用于后续画图展示物理位置
    coords = df[['x', 'y']].values
    print(f"✅ 成功获取节点总数: {num_nodes} 个")
except Exception as e:
    print(f"❌ 读取 Excel 失败: {e}")
    import sys

    sys.exit()

# ----------------- 2. 生成逼真的模拟交通流数据 -----------------
days = 3
intervals_per_hour = 12
total_steps = days * 24 * intervals_per_hour
steps_per_day = 24 * intervals_per_hour

print(f"\n正在生成 {num_nodes} 个节点，连续 {days} 天的模拟交通流量数据...")
traffic_data = np.zeros((num_nodes, total_steps))
time_axis = np.linspace(0, 2 * np.pi, steps_per_day)

for i in range(num_nodes):
    base_flow = np.random.uniform(50, 200)
    morning_peak = np.maximum(0, np.sin(time_axis - np.pi / 4)) * np.random.uniform(100, 300)
    evening_peak = np.maximum(0, np.sin(time_axis - np.pi)) * np.random.uniform(150, 400)

    daily_pattern = base_flow + morning_peak + evening_peak
    node_series = np.tile(daily_pattern, days)

    noise = np.random.normal(0, base_flow * 0.15, total_steps)
    node_series = np.maximum(0, node_series + noise)
    traffic_data[i, :] = node_series

# ----------------- 3. 计算 DTW 语义相似图 -----------------
print(f"\n✅ 模拟流量数据生成完毕！")
print(f"正在计算 DTW 语义相似图... (需计算约 {num_nodes * (num_nodes - 1) // 2} 次，请耐心等待 1~3 分钟)")

dtw_matrix = np.zeros((num_nodes, num_nodes))

for i in range(num_nodes):
    if i % 20 == 0:
        print(f"  -> 已处理 {i}/{num_nodes} 个节点...")
    for j in range(i + 1, num_nodes):
        distance, _ = fastdtw(traffic_data[i], traffic_data[j])
        dtw_matrix[i, j] = distance
        dtw_matrix[j, i] = distance

print("\nDTW 距离计算完成，正在进行归一化并生成连通图...")

min_val = np.min(dtw_matrix)
max_val = np.max(dtw_matrix)
norm_dtw = (dtw_matrix - min_val) / (max_val - min_val + 1e-8)

# 语义连接阈值
THRESHOLD = 0.07
semantic_graph = np.where(norm_dtw < THRESHOLD, 1.0, 0.0)
np.fill_diagonal(semantic_graph, 1.0)

# ----------------- 4. 保存 .npy 矩阵 (模型训练用) -----------------
np.save('../data/mock_traffic_data.npy', traffic_data)
np.save('../data/dtw_adj.npy', semantic_graph)
print(f"✅ 已保存特征矩阵: mock_traffic_data.npy 和 dtw_adj.npy")

# ----------------- 5. 生成可视化图片和 HTML (论文与演示用) -----------------
print("\n正在生成可视化图表...")

# 提取不需要画自环的矩阵（专门用来画图）
vis_matrix = semantic_graph.copy()
np.fill_diagonal(vis_matrix, 0.0)

# 准备节点坐标字典
pos = {i: (coords[i, 0], coords[i, 1]) for i in range(num_nodes)}

# --- A. 生成 .png 静态图片 ---
plt.figure(figsize=(10, 8))
G = nx.from_numpy_array(vis_matrix)
nx.draw(G, pos, node_size=20, node_color='#ff7f0e', edge_color='#ffbb78', alpha=0.6, with_labels=False)
plt.title(f"Shanghai Bridge DTW Semantic Network (Threshold={THRESHOLD})", fontsize=14)
plt.axis('equal')
plt.tight_layout()
plt.savefig('dtw_graph_visualization.png', dpi=300, bbox_inches='tight')
print("✅ 已保存静态图片: dtw_graph_visualization.png")
plt.close()

# --- B. 生成 .html 交互式页面 (Plotly) ---
try:
    import plotly.graph_objects as go

    edge_x, edge_y = [], []
    rows, cols = np.where(vis_matrix == 1)
    for r, c in zip(rows, cols):
        if r < c:  # 避免画双向重叠边
            x0, y0 = coords[r]
            x1, y1 = coords[c]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#ffbb78'),
        hoverinfo='none', mode='lines'
    )

    node_trace = go.Scatter(
        x=coords[:, 0], y=coords[:, 1],
        mode='markers', hoverinfo='text',
        marker=dict(color='#ff7f0e', size=6, line=dict(width=0.5, color='white'))
    )
    # 添加悬停文本，展示节点索引和坐标
    node_trace.text = [f"Bridge {i}<br>x: {coords[i, 0]:.4f}<br>y: {coords[i, 1]:.4f}" for i in range(num_nodes)]

    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        # 修复: 在新版 plotly 中，字体属性应嵌套在 title 字典中
                        title=dict(
                            text=f'<br>DTW Semantic Network (Threshold={THRESHOLD})',
                            font=dict(size=16, color='white')
                        ),
                        showlegend=False, hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        plot_bgcolor="#1e1e1e", paper_bgcolor="#1e1e1e",
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
                    )
                    )
    fig.write_html("dtw_interactive_graph.html")
    print("✅ 已保存交互式页面: dtw_interactive_graph.html")
except ImportError:
    print("⚠️ 未安装 plotly，已跳过 HTML 文件生成。")

print("\n🎉 第二步【时间特征生成与语义图构建】大功告成！")