import numpy as np
import pandas as pd
import os
from sklearn.linear_model import LogisticRegression

# ==========================================
# 1. 初始化路径与基础数据 (复用你现有的逻辑)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data_shanghai")
TRAFFIC_DIR = os.path.join(DATA_DIR, "data_traffic")

node_embeddings = pd.read_excel(os.path.join(DATA_DIR, "node_embeddings_shanghai.xlsx"), index_col=0).fillna(0.0).values
adjacency_matrix = pd.read_csv(os.path.join(DATA_DIR, "link_matrix_shanghai.csv"), index_col=0).fillna(0).values


# 复用你的 cosine_similarity 和 compute_factors 函数
def cosine_similarity(z_i, z_j):
    norm_i = np.linalg.norm(z_i)
    norm_j = np.linalg.norm(z_j)
    if norm_i == 0 or norm_j == 0:
        return 0.0
    return np.dot(z_i, z_j) / (norm_i * norm_j)


def compute_factors(traffic_flow, congestion_index, adjacency_matrix, node_embeddings):
    num_nodes = len(traffic_flow)
    x_factors = np.zeros(num_nodes)
    y_factors = np.zeros(num_nodes)

    for i in range(num_nodes):
        n_i_t = traffic_flow[i]
        s_i_t = congestion_index[i]
        x_i_t = 0
        y_i_t = 0

        for j in range(num_nodes):
            if adjacency_matrix[i, j] == 1:
                sim = cosine_similarity(node_embeddings[i], node_embeddings[j])
                n_j_t = traffic_flow[j]
                prev_flow = traffic_flow[i - 1] if i > 0 else traffic_flow[0]

                x_i_t += sim * s_i_t * n_j_t + n_i_t - prev_flow
                y_i_t += sim * s_i_t * n_j_t - n_i_t + prev_flow

        x_factors[i] = x_i_t / n_i_t if n_i_t != 0 else 0
        y_factors[i] = y_i_t / n_i_t if n_i_t != 0 else 0

    return x_factors, y_factors


def load_data_at_t(t):
    file_path = os.path.join(TRAFFIC_DIR, f"shanghaidata_{t}.xlsx")
    if not os.path.exists(file_path):
        return None
    data = pd.read_excel(file_path)
    flow = data['flow'].fillna(0.0).values
    congestion = data['congestion'].fillna(1).values
    return flow, congestion


# ==========================================
# 2. 构造训练数据集
# ==========================================
print("正在读取历史数据并构建训练集...")
X_c_list, Y_c_list = [], []
X_h_list, Y_h_list = [], []

t = 0
while True:
    data_t = load_data_at_t(t)
    data_t_plus_1 = load_data_at_t(t + 1)

    # 如果找不到 t 或 t+1 的数据，说明遍历到文件末尾，退出循环
    if data_t is None or data_t_plus_1 is None:
        break

    flow_t, cong_t = data_t
    flow_next, cong_next = data_t_plus_1

    # 计算 t 时刻的 x 和 y 因子
    x_factors, y_factors = compute_factors(flow_t, cong_t, adjacency_matrix, node_embeddings)

    # 提取标签：下一时刻是否变堵 / 是否恢复
    # cong_next > cong_t 视为变堵(1)，否则(0)
    y_c = (cong_next > cong_t).astype(int)

    # cong_next < cong_t 视为恢复(1)，否则(0)
    y_h = (cong_next < cong_t).astype(int)

    X_c_list.extend(x_factors)
    Y_c_list.extend(y_c)

    X_h_list.extend(y_factors)
    Y_h_list.extend(y_h)

    t += 1

# 转换为 sklearn 所需的 numpy 格式 (N, 1)
X_c = np.array(X_c_list).reshape(-1, 1)
Y_c = np.array(Y_c_list)
X_h = np.array(X_h_list).reshape(-1, 1)
Y_h = np.array(Y_h_list)

print(f"训练集构建完成。共提取 {len(X_c)} 个样本。")

# ==========================================
# 3. 训练逻辑回归模型与参数转换
# ==========================================
print("正在训练模型...")

# 使用 class_weight='balanced' 是因为路况不变(0)的样本远多于路况变化(1)的样本
model_c = LogisticRegression(class_weight='balanced')
model_c.fit(X_c, Y_c)

model_h = LogisticRegression(class_weight='balanced')
model_h.fit(X_h, Y_h)

# 提取 P_c 模型的权重和偏置
w_c = model_c.coef_[0][0]
b_c = model_c.intercept_[0]

# 提取 P_h 模型的权重和偏置
w_h = model_h.coef_[0][0]
b_h = model_h.intercept_[0]

# 根据公式映射转换为 p1, p2, p3, p4
p1_opt = -w_c
p3_opt = b_c / w_c if w_c != 0 else 0

p2_opt = -w_h
p4_opt = b_h / w_h if w_h != 0 else 0

# ==========================================
# 4. 输出最优参数
# ==========================================
print("\n=== 上海专属最优参数训练结果 ===")
print(f"p1_opt = {p1_opt}")
print(f"p2_opt = {p2_opt}")
print(f"p3_opt = {p3_opt}")
print(f"p4_opt = {p4_opt}")
print("================================")
print("请将上方参数替换到你的主仿真脚本中。")