# test_spread_core_shenzhen.py
import pandas as pd
import numpy as np
import networkx as nx
import math
import json
import os
import time
from collections import deque
import matplotlib
matplotlib.use('Agg')  # 必须在 import pyplot 之前，强制禁止弹出本地 GUI 窗口
import matplotlib.pyplot as plt

matplotlib.use('TkAgg')
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib import animation

# ----------------- 动态路径配置（本地和服务器通用） -----------------
try:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    DATA_DIR = "."

OUTPUT_DIR = os.path.join(DATA_DIR, "data_shanghai/output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ----------------- 数据读取与强制格式清洗 -----------------
def clean_id(x):
    try:
        return str(int(float(x)))
    except:
        return str(x).strip()


nodes_df = pd.read_excel(os.path.join(DATA_DIR, "data_shanghai/Shanghai_Bridge_List_Averages.xlsx"))
nodes_df['node'] = nodes_df['node'].apply(clean_id)

link_matrix = pd.read_csv(os.path.join(DATA_DIR, "data_shanghai/link_matrix_shanghai.csv"), index_col=0)
link_matrix.index = link_matrix.index.map(clean_id)
link_matrix.columns = link_matrix.columns.map(clean_id)
88
# ----------------- 构建拓扑图 -----------------
G = nx.Graph()

for _, row in nodes_df.iterrows():
    G.add_node(row['node'], pos=(row['x'], row['y']))

# 安全锁：确保只连接合法节点
valid_nodes = set(G.nodes)

# 💡 核心修复 2：只要权重大于 0 就说明有连接，不再强求等于 1
ii, jj = np.where(link_matrix.values > 0)
rows = link_matrix.index.to_list()
cols = link_matrix.columns.to_list()

for i, j in zip(ii, jj):
    n1, n2 = rows[i], cols[j]
    if n1 != n2 and (n1 in valid_nodes) and (n2 in valid_nodes):
        G.add_edge(n1, n2)

pos = nx.get_node_attributes(G, 'pos')

# 打印质检信息
print(f"\n📊 数据质检: 成功加载了 {G.number_of_nodes()} 座桥，连接成了 {G.number_of_edges()} 条线！\n")


# ----------------- 核心扩散算法 -----------------
def calculate_distance(node1, node2, pos):
    x1, y1 = pos[node1]
    x2, y2 = pos[node2]
    return np.hypot(x2 - x1, y2 - y1)


def distribute_flow(node, flow, visited, pos):
    neighbors = [n for n in G.neighbors(node) if n not in visited]
    if not neighbors:
        return {}
    inv = {}
    tot = 0.0
    for nei in neighbors:
        d = calculate_distance(node, nei, pos)
        if d > 0:
            inv_val = 1.0 / d
            inv[nei] = inv_val
            tot += inv_val
    if tot == 0:
        return {}
    return {nei: (inv[nei] / tot) * flow for nei in inv}


def spread_traffic(event_node, spread_flow, pos, max_steps=332):
    visited = set()
    flow_results = {n: 0.0 for n in G.nodes}
    spread_sequence = []

    q = deque()
    q.append((event_node, spread_flow))

    steps = 0
    while q and steps < max_steps:
        cur, cur_flow = q.popleft()
        if cur in visited:
            continue
        visited.add(cur)

        flow_results[cur] += cur_flow
        spread_sequence.append((cur, cur_flow))

        distributed = distribute_flow(cur, cur_flow, visited, pos)
        for nei, f in distributed.items():
            flow_results[nei] += f
            q.append((nei, f))

        steps += 1

    return spread_sequence, flow_results


# ----------------- 可视化与动画导出 -----------------
def fit_view(ax, pos, pad_ratio=0.08, equal=True, flip_y=False):
    coords = np.array([pos[n] for n in pos], dtype=float)
    xs, ys = coords[:, 0], coords[:, 1]
    x_min, x_max = xs.min(), xs.max()
    y_min, y_max = ys.min(), ys.max()
    x_pad = (x_max - x_min) * pad_ratio if (x_max > x_min) else 1.0
    y_pad = (y_max - y_min) * pad_ratio if (y_max > y_min) else 1.0
    ax.set_xlim(x_min - x_pad, x_max + x_pad)
    ax.set_ylim(y_min - y_pad, y_max + y_pad)
    if equal:
        ax.set_aspect('equal', adjustable='box')
    if flip_y:
        ax.invert_yaxis()


def create_animation(spread_sequence, pos, G,
                     save_path, max_frames=100, fps=10,
                     figsize=(8, 6), dpi=80, show_labels=False):
    nodes = list(G.nodes)
    idx = {n: i for i, n in enumerate(nodes)}
    coords = np.array([pos[n] for n in nodes], dtype=float)

    base_color = np.array([0.7, 0.7, 0.7, 1.0])
    active_color = np.array([1.0, 0.0, 0.0, 1.0])
    colors = np.tile(base_color, (len(nodes), 1))

    segments = [[pos[u], pos[v]] for u, v in G.edges]
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    lc = LineCollection(segments, linewidths=0.8, colors=(0.7, 0.7, 0.7, 1.0), zorder=1)
    ax.add_collection(lc)

    scat = ax.scatter(coords[:, 0], coords[:, 1], s=40, zorder=2)
    scat.set_facecolors(colors)
    scat.set_edgecolors((0.3, 0.3, 0.3, 1.0))

    if show_labels:
        for n, (x, y) in pos.items():
            ax.text(x, y, n, fontsize=7, ha='center', va='center', zorder=3)

    fit_view(ax, pos)

    title = ax.text(0.02, 0.98, "", transform=ax.transAxes, va='top', fontsize=11)

    total_steps = len(spread_sequence)
    group_steps = max(1, math.ceil(total_steps / max_frames))
    frame_chunks = [spread_sequence[i:i + group_steps] for i in range(0, total_steps, group_steps)]
    real_frames = len(frame_chunks)

    def init():
        title.set_text("Traffic Spread: init")
        # 💡 核心修复：每次动画从头开始时，把所有节点强制洗回灰色！
        colors[:] = base_color
        scat.set_facecolors(colors)
        return [scat, lc, title]

    def update(frame):
        nodes_to_update = frame_chunks[frame]
        for node, _ in nodes_to_update:
            i = idx[node]
            colors[i] = active_color
        scat.set_facecolors(colors)
        title.set_text(f"Step {frame + 1}/{real_frames}")
        return [scat, lc, title]

    ani = animation.FuncAnimation(
        fig, update, init_func=init,
        frames=real_frames,
        interval=1000 // fps,
        blit=False,
        repeat=True,  # 开启循环播放
        cache_frame_data=False
    )

    writer = animation.PillowWriter(fps=fps)
    ani.save(save_path, writer=writer, dpi=dpi)

    print("🎬 正在弹窗播放传播动画...")
   # plt.show()  # 弹出独立窗口实时演示
    plt.close(fig)


# ----------------- 主控入口 -----------------
def run_spread(event_node: str, event_type: int) -> dict:
    if event_node not in nodes_df['node'].values:
        raise ValueError(f"当前节点 {event_node} 在你的 Excel 数据中不存在，请检查输入！")

    initial_flow = 100
    if event_type == 1:
        remaining_flow = initial_flow * 0.8
    elif event_type == 2:
        remaining_flow = initial_flow * 0.5
    elif event_type == 3:
        remaining_flow = initial_flow * 0.0
    else:
        raise ValueError("event_type 必须是 1, 2 或 3")

    spread_flow = initial_flow - remaining_flow

    spread_sequence, _ = spread_traffic(event_node, spread_flow, pos)
    gif_path = os.path.join(OUTPUT_DIR, "spread_animation.gif")

    create_animation(spread_sequence, pos, G, save_path=gif_path)

    seen = set()
    unique_nodes = []
    for node, _ in spread_sequence:
        if node not in seen:
            unique_nodes.append(node)
            seen.add(node)

    sequence_with_step = [{"step": i + 1, "node": n} for i, n in enumerate(unique_nodes)]

    output = {
        "spread_sequence": sequence_with_step,
        "gif_path": "output/spread_animation.gif"
    }

    with open(os.path.join(OUTPUT_DIR, "spread_sequence.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    return output


if __name__ == "__main__":
    import sys

    # 如果通过命令行传了参数（比如在服务器上跑），就优先用命令行的
    if len(sys.argv) >= 3:
        node = sys.argv[1]
        typ = int(sys.argv[2])
    else:
        # 如果是本地直接点击运行，则进入“交互选择模式”
        print("\n" + "=" * 50)
        print("💡 进入本地交互测试模式")
        print("=" * 50)

        # 1. 让用户输入节点
        user_node = input("👉 请输入起始【节点编号】 (例如 0, 1, 100，直接回车默认用 0): ").strip()
        node = user_node if user_node else "0"

        # 2. 让用户输入事件类型
        user_typ = input("👉 请输入【事件类型】 (1, 2 或 3，直接回车默认用 2): ").strip()
        if not user_typ:
            typ = 2
        else:
            try:
                typ = int(user_typ)
            except ValueError:
                print("⚠️ 输入的事件类型不合法，自动回退到默认类型 2")
                typ = 2

        print(f"\n🚀 正在测试 -> 起始节点: {node}, 事件类型: {typ}")
        print("=" * 50 + "\n")

    # 执行主程序
    try:
        result = run_spread(node, typ)
        print("\n✅ 运行完成！输出结果 JSON 如下：")
        print(json.dumps(result, ensure_ascii=False, indent=4))
    except Exception as e:
        print(f"\n❌ 运行失败: {e}")
