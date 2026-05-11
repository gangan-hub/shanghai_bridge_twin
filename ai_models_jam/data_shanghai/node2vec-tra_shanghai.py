import os
import pandas as pd
import numpy as np
import networkx as nx
import random
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, calinski_harabasz_score
from gensim.models import Word2Vec
import matplotlib.pyplot as plt
from skopt import gp_minimize
from skopt.space import Real
from skopt.utils import use_named_args
from mpl_toolkits.mplot3d import Axes3D
from bayes_opt import BayesianOptimization

# 设置全局随机种子
SEED = 42
random.seed(SEED)
np.random.seed(SEED)


# 读取节点和邻接矩阵数据
def load_graph_with_features(node_excel_path, adj_csv_path):
    # 【修改】：使用 fillna(0) 清洗掉 Excel 中的所有空值(NaN)
    node_df = pd.read_excel(node_excel_path).fillna(0)
    node_attrs = {}
    coords = {}
    for _, row in node_df.iterrows():
        node_id = str(row['node'])
        coords[node_id] = (row['x'], row['y'])
        node_attrs[node_id] = {
            'flow': float(row['flow']),
            'congestion': float(row['congestion']),
            'poi': float(row['poi'])
        }

    adj_df = pd.read_csv(adj_csv_path, index_col=0)
    adj_df.index = adj_df.index.map(str)
    adj_df.columns = adj_df.columns.map(str)

    G = nx.Graph()

    # 先添加所有节点
    for node_id in coords:
        G.add_node(node_id)

    for i in adj_df.index:
        for j in adj_df.columns:
            if adj_df.loc[i, j] == 1:
                i_str, j_str = str(i), str(j)
                if i_str not in coords or j_str not in coords:
                    continue

                # 计算两点之间的距离
                dist = np.linalg.norm(np.array(coords[i_str]) - np.array(coords[j_str]))

                # 安全计算距离倒数（避免除以0，设置一个极小值阈值 1e-5）
                dist_inv = 1.0 / dist if dist > 1e-5 else 1.0

                # 安全计算邻接节点总距离倒数
                neighbors = list(G.neighbors(j_str))
                dist_inv_sum = 0.0
                if neighbors:
                    for nei in neighbors:
                        nei_dist = np.linalg.norm(np.array(coords[j_str]) - np.array(coords[nei]))
                        dist_inv_sum += (1.0 / nei_dist if nei_dist > 1e-5 else 1.0)
                else:
                    dist_inv_sum = 1.0

                # 归一化得到权重
                weight = dist_inv / dist_inv_sum if dist_inv_sum > 0 else 1.0

                # 确保 weight 不是 nan 或 inf
                if np.isnan(weight) or np.isinf(weight):
                    weight = 1.0

                G.add_edge(i_str, j_str, distance=dist, weight=weight)

    nx.set_node_attributes(G, node_attrs)
    return G


# 自定义随机游走类
class RandomWalker:
    def __init__(self, G, p, q, r1, r2, r3, r4):
        self.G = G
        self.p = p
        self.q = q
        self.r1 = r1
        self.r2 = r2
        self.r3 = r3
        self.r4 = r4

    def walk(self, start_node, walk_length):
        walk = [start_node]
        while len(walk) < walk_length:
            cur = walk[-1]
            neighbors = list(self.G.neighbors(cur))
            if not neighbors:
                break
            if len(walk) == 1:
                walk.append(random.choice(neighbors))
            else:
                prev = walk[-2]
                probs = self.transition_probs(prev, cur, neighbors)
                next_node = random.choices(neighbors, weights=probs, k=1)[0]
                walk.append(next_node)
        return walk

    def transition_probs(self, prev, cur, neighbors):
        probs = []
        cur_attr = self.G.nodes[cur]
        for nei in neighbors:
            nei_attr = self.G.nodes[nei]
            weight = float(self.G[cur][nei]['weight'])

            # 计算属性比率，加入安全检查
            ratio_flow = nei_attr['flow'] / (cur_attr['flow'] + 1e-5)
            ratio_cong = nei_attr['congestion'] / (cur_attr['congestion'] + 1e-5)
            ratio_poi = nei_attr['poi'] / (cur_attr['poi'] + 1e-5)

            # Node2Vec 返回概率核心算法
            if nei == prev:
                score = self.r1 * weight / self.p + self.r2 * ratio_flow + self.r3 * ratio_cong + self.r4 * ratio_poi
            elif self.G.has_edge(prev, nei):
                score = self.r1 * weight + self.r2 * ratio_flow + self.r3 * ratio_cong + self.r4 * ratio_poi
            else:
                score = self.r1 * weight / self.q + self.r2 * ratio_flow + self.r3 * ratio_cong + self.r4 * ratio_poi

            # 【核心修复】：拦截所有 nan 或 inf 异常值，并保证权重大于 0
            if np.isnan(score) or np.isinf(score):
                score = 1e-5
            score = max(score, 1e-5)

            probs.append(score)

        return probs


# Node2Vec主类
class Node2Vec:
    def __init__(self, G, p, q, r1, r2, r3, r4, dimensions=3, walk_length=50, num_walks=10):
        self.G = G
        self.p = p
        self.q = q
        self.r1 = r1
        self.r2 = r2
        self.r3 = r3
        self.r4 = r4
        self.dimensions = dimensions
        self.walk_length = walk_length
        self.num_walks = num_walks

    def train(self):
        walker = RandomWalker(self.G, self.p, self.q, self.r1, self.r2, self.r3, self.r4)
        walks = []
        nodes = list(self.G.nodes())
        for _ in range(self.num_walks):
            random.shuffle(nodes)
            for node in nodes:
                walks.append(walker.walk(node, self.walk_length))
        self.model = Word2Vec(walks, vector_size=self.dimensions, window=5, min_count=0, sg=1, workers=1, seed=SEED)
        return self.model

    def get_embeddings(self):
        return {node: self.model.wv[node] for node in self.G.nodes if node in self.model.wv}


# 聚类评估
# DBI：越小越好（表示类内紧凑、类间分离）
# CHI：越大越好（同样代表类间大于类内）
def evaluate_embeddings(embeddings, n_clusters=5):
    X = np.array(list(embeddings.values()))
    kmeans = KMeans(n_clusters=n_clusters, random_state=SEED).fit(X)
    labels = kmeans.labels_
    dbi = davies_bouldin_score(X, labels)
    chi = calinski_harabasz_score(X, labels)
    return dbi, chi


# 贝叶斯优化（搜索最优p，q）
def bayesian_optimize_pq(graphs, n_calls=30):
    # 定义搜索空间
    space = [
        Real(2.0, 4.0, name='p'),
        Real(0.01, 1.0, name='q')
    ]

    best_result = {"score": -np.inf}

    # 用于记录每次评估结果
    p_list, q_list, dbi_list, chi_list, score_list = [], [], [], [], []

    @use_named_args(space)
    def objective(p, q):
        print(f"Evaluating: p={p:.3f}, q={q:.3f}")
        try:
            # 合并所有图
            G = nx.compose_all(graphs)
            n2v = Node2Vec(G, p, q, 1, 1, 1, 1)
            n2v.train()
            embeddings = n2v.get_embeddings()
            if not embeddings:
                return 1e6  # 若无嵌入结果，返回高损失
            dbi, chi = evaluate_embeddings(embeddings)
            score = chi / (dbi + 1e-5)
            print(f"Score = {score:.4f}, DBI = {dbi:.4f}, CHI = {chi:.4f}")

            # 记录参数和评估值
            p_list.append(p)
            q_list.append(q)
            dbi_list.append(dbi)
            chi_list.append(chi)
            score_list.append(score)

            if score > best_result["score"]:
                best_result["score"] = score
                best_result["p"] = p
                best_result["q"] = q
        except Exception as e:
            print(f"Error for p={p:.3f}, q={q:.3f}: {e}")
            return 1e6  # 错误时返回高损失

        return -score

        # 执行贝叶斯优化

    res = gp_minimize(
        objective,
        space,
        n_calls=n_calls,
        random_state=SEED,
        acq_func="EI"  # Expected Improvement
    )

    print(f"\n=== 贝叶斯优化找到的最优参数 ===")
    print(f"Best p = {best_result['p']:.4f}, Best q = {best_result['q']:.4f}, Score = {best_result['score']:.4f}")

    # 画3D 图
    fig = plt.figure(figsize=(14, 4))
    ax1 = fig.add_subplot(131, projection='3d')
    ax1.scatter(p_list, q_list, dbi_list, c=dbi_list, cmap='viridis')
    ax1.set_title("DBI vs p, q")
    ax1.set_xlabel("p")
    ax1.set_ylabel("q")
    ax1.set_zlabel("DBI")

    ax2 = fig.add_subplot(132, projection='3d')
    ax2.scatter(p_list, q_list, chi_list, c=chi_list, cmap='plasma')
    ax2.set_title("CHI vs p, q")
    ax2.set_xlabel("p")
    ax2.set_ylabel("q")
    ax2.set_zlabel("CHI")

    ax3 = fig.add_subplot(133, projection='3d')
    ax3.scatter(p_list, q_list, score_list, c=score_list, cmap='coolwarm')
    ax3.set_title("Score vs p, q")
    ax3.set_xlabel("p")
    ax3.set_ylabel("q")
    ax3.set_zlabel("Score")

    plt.tight_layout()
    plt.show()

    return best_result  # 返回包含 p 和 q 的字典


# 贝叶斯优化（搜索最优r1-r4）
def bayesian_optimize_r1234(G, p, q, init_points=5, n_iter=15):
    history = []

    def objective(r1, r2, r3, r4):
        try:
            n2v = Node2Vec(G, p, q, r1, r2, r3, r4)
            n2v.train()
            embeddings = n2v.get_embeddings()
            if not embeddings:
                return -np.inf
            dbi, chi = evaluate_embeddings(embeddings)
            score = chi / (dbi + 1e-5)
            history.append({
                'r1': r1, 'r2': r2, 'r3': r3, 'r4': r4,
                'DBI': dbi, 'CHI': chi, 'Score': score
            })
            print(
                f"[r1={r1:.3f}, r2={r2:.3f}, r3={r3:.3f}, r4={r4:.3f}] => DBI={dbi:.4f}, CHI={chi:.4f}, Score={score:.4f}")
            return score
        except Exception as e:
            print(f"Exception for r1–r4: {e}")
            return -np.inf

    optimizer = BayesianOptimization(
        f=objective,
        pbounds={
            'r1': (0.25, 1.0),
            'r2': (0.25, 1.0),
            'r3': (0.25, 1.0),
            'r4': (0.25, 1.0),
        },
        verbose=2,
        random_state=42
    )

    optimizer.maximize(init_points=init_points, n_iter=n_iter)

    best_params = optimizer.max['params']
    best_score = optimizer.max['target']

    print("\n=== 最优 r1–r4 参数 ===")
    print(
        f"Best r1={best_params['r1']:.4f}, r2={best_params['r2']:.4f}, r3={best_params['r3']:.4f}, r4={best_params['r4']:.4f} with Score={best_score:.4f}")

    plot_sorted_param_line_relationship(history)

    return best_params


def plot_sorted_param_line_relationship(history):
    def get_sorted_lists(param_name):

        # 取出参数和对应的 DBI、CHI，按参数值升序排序
        pairs = sorted([(h[param_name], h['DBI'], h['CHI'], h['Score']) for h in history], key=lambda x: x[0])
        param_vals = [p[0] for p in pairs]
        dbis = [p[1] for p in pairs]
        chis = [p[2] for p in pairs]
        scores = [p[3] for p in pairs]
        return param_vals, dbis, chis, scores

    fig, axs = plt.subplots(4, 3, figsize=(18, 16))
    param_names = ['r1', 'r2', 'r3', 'r4']
    colors = {'DBI': 'red', 'CHI': 'blue', 'Score': 'green'}
    metrics = ['DBI', 'CHI', 'Score']

    for row, param in enumerate(param_names):
        xs, dbis, chis, scores = get_sorted_lists(param)
        ys_all = [dbis, chis, scores]
        for col, (metric, ys) in enumerate(zip(metrics, ys_all)):
            axs[row, col].plot(xs, ys, marker='o', color=colors[metric])
            axs[row, col].set_title(f'{param} vs {metric}')
            axs[row, col].set_xlabel(param)
            axs[row, col].set_ylabel(metric)
            axs[row, col].grid(True)

    plt.tight_layout()
    plt.show()


# 合并多个图的函数，保留节点和边，合并不同图的节点属性
def merge_graphs(graphs):
    merged_graph = graphs[0]

    for G in graphs[1:]:
        for node in G.nodes:
            # 更新节点属性（合并不同图中的flow, congestion, poi等数据）
            if node in merged_graph.nodes:
                merged_graph.nodes[node]['flow'] += G.nodes[node]['flow']
                merged_graph.nodes[node]['congestion'] += G.nodes[node]['congestion']
                merged_graph.nodes[node]['poi'] += G.nodes[node]['poi']
            else:
                merged_graph.add_node(node, **G.nodes[node])

    return merged_graph


# 主程序
if __name__ == '__main__':

    # 动态获取当前脚本所在的文件夹路径 (即 F:\桌面\Python\V_STGRN_Project\武汉备份\)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # 1. 相对路径加载节点数据文件（这里将原本的多个文件循环，改为了单个你的目标文件并放入列表以兼容代码逻辑）
    node_excel_paths = [os.path.join(BASE_DIR, 'Shanghai_Bridge_List_Averages.xlsx')]

    # 2. 相对路径加载邻接矩阵文件
    adj_csv_path = os.path.join(BASE_DIR, 'link_matrix_shanghai.csv')

    # 加载图
    graphs = [load_graph_with_features(path, adj_csv_path) for path in node_excel_paths]

    # 合并图 (这里虽然只有1个图，但保留调用合并函数不影响执行)
    G = merge_graphs(graphs)

    print("\n=== Step 1: 搜索 p 和 q ===")
    best_result = bayesian_optimize_pq(graphs, n_calls=30)
    best_p = best_result['p']
    best_q = best_result['q']

    print(f"\n最优 p, q = ({best_p}, {best_q})")

    print("\n=== Step 2: 搜索 r1-r4 ===")
    best_r_dict = bayesian_optimize_r1234(G, best_p, best_q)
    best_r1, best_r2, best_r3, best_r4 = best_r_dict['r1'], best_r_dict['r2'], best_r_dict['r3'], best_r_dict['r4']

    print(f"\n最优 r1-r4 = ({best_r1}, {best_r2}, {best_r3}, {best_r4})")

    print("\n=== 最终模型训练与评估 ===")

    # 使用最优参数训练最终模型
    final_model = Node2Vec(G, best_p, best_q, best_r1, best_r2, best_r3, best_r4)
    final_model.train()
    final_embs = final_model.get_embeddings()

    dbi, chi = evaluate_embeddings(final_embs)
    print(f"\nFinal DBI: {dbi:.4f}, Final CHI: {chi:.4f}")

    print("\n=== 每个节点的嵌入向量 ===")
    for node, emb in final_embs.items():
        print(f"{node}: {emb}")

    # 保存嵌入向量为 DataFrame 并导出为 Excel (同样保存在当前目录下)
    emb_df = pd.DataFrame.from_dict(final_embs, orient='index')
    emb_df.index.name = 'node'
    emb_df.columns = [f'dim_{i + 1}' for i in range(emb_df.shape[1])]

    output_path = os.path.join(BASE_DIR, 'node_embeddings_shanghai.xlsx')
    emb_df.to_excel(output_path)
    print(f"\n嵌入向量已保存至 {output_path}")