import numpy as np
import pandas as pd
import json
import sys
import os
import random
import io

# =====================================================================
# 1. 系统与环境初始化 (上海版)
# =====================================================================

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data_shanghai")
TRAFFIC_DIR = os.path.join(DATA_DIR, "data_traffic")

node_embeddings = pd.read_excel(os.path.join(DATA_DIR, "node_embeddings_shanghai.xlsx"), index_col=0).fillna(0.0).values
adjacency_matrix = pd.read_csv(os.path.join(DATA_DIR, "link_matrix_shanghai.csv"), index_col=0).fillna(0).values


# =====================================================================
# 2. 核心功能函数定义
# =====================================================================

def get_t_by_weekday_and_time(target_weekday, target_hour, target_minute):
    t = 0
    while True:
        file_path = os.path.join(TRAFFIC_DIR, f"shanghaidata_{t}.xlsx")

        if not os.path.exists(file_path):
            break
        try:
            df = pd.read_excel(file_path, nrows=1)
            if 'timestamp' in df.columns:
                first_timestamp = pd.to_datetime(df['timestamp'].iloc[0])
                file_weekday = first_timestamp.dayofweek + 1
                file_hour = first_timestamp.hour
                file_minute = first_timestamp.minute

                rounded_minute = 0 if file_minute < 30 else 30

                if file_weekday == target_weekday and file_hour == target_hour and rounded_minute == target_minute:
                    return t
        except Exception:
            pass
        t += 1

    raise ValueError(f"未找到 星期{target_weekday} 且 时间为 {target_hour:02d}:{target_minute:02d} 的上海数据文件")


def load_traffic_and_congestion_data(t):
    file_path = os.path.join(TRAFFIC_DIR, f"shanghaidata_{t}.xlsx")
    data = pd.read_excel(file_path)

    traffic_flow = data['flow'].fillna(0.0).values.copy() if 'flow' in data.columns else np.zeros(len(data))
    congestion_index = data['congestion'].fillna(1).values.copy() if 'congestion' in data.columns else np.ones(
        len(data))
    free_flow = data['free-flow speed'].fillna(40.0).values.copy() if 'free-flow speed' in data.columns else np.full(
        len(data), 40.0)
    jam_density = data['jam density'].fillna(100.0).values.copy() if 'jam density' in data.columns else np.full(
        len(data), 100.0)

    return traffic_flow, congestion_index, free_flow, jam_density


def cosine_similarity(z_i, z_j):
    norm_i = np.linalg.norm(z_i)
    norm_j = np.linalg.norm(z_j)
    if norm_i == 0 or norm_j == 0:
        return 0.0
    return np.dot(z_i, z_j) / (norm_i * norm_j)


def compute_factors(t, node_embeddings, traffic_flow, congestion_index, adjacency_matrix):
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


def logistic_regression(x_factors, y_factors, p1, p2, p3, p4):
    P_c = 1 / (1 + np.exp(p1 * (x_factors + p3)))
    P_h = 1 / (1 + np.exp(p2 * (y_factors + p4)))
    return P_c, P_h


def update_congestion_index_dynamic(P_c, P_h, current_congestion, adjacency_matrix, is_accident_active):
    num_nodes = len(current_congestion)
    modified_Pc = np.array(P_c).copy().reshape(-1)
    modified_Ph = np.array(P_h).copy().reshape(-1)

    for i in range(num_nodes):
        congested_neighbors = 0
        free_neighbors = 0

        for j in range(num_nodes):
            if adjacency_matrix[i, j] > 0 and i != j:
                if current_congestion[j] >= 3:
                    congested_neighbors += 1
                if current_congestion[j] <= 2:
                    free_neighbors += 1

        if congested_neighbors > 0:
            modified_Pc[i] = min(modified_Pc[i] + 0.6, 0.98)
            modified_Ph[i] = max(modified_Ph[i] - 0.5, 0.02)

        if not is_accident_active and current_congestion[i] >= 3:
            if free_neighbors > 0:
                modified_Ph[i] = 0.9
                modified_Pc[i] = 0.05
            else:
                modified_Ph[i] = 0.05

    c_i_t = np.random.binomial(1, modified_Pc).reshape(-1)
    h_i_t = np.random.binomial(1, modified_Ph).reshape(-1)
    s_i_t = np.array(current_congestion).reshape(-1)

    s_i_t_plus_1 = np.clip(s_i_t + c_i_t - h_i_t, 1, 4)
    return s_i_t_plus_1.astype(int)


def simulate_traffic_metrics(predicted_congestion, free_flow, jam_density, modifiable_node, is_accident_active):
    results = []

    for i in range(len(predicted_congestion)):
        pred_c = int(np.ravel(predicted_congestion[i])[0])

        if i == modifiable_node and is_accident_active:
            v_new = 0.0
            q_new = 0.0
            pred_c = 4
        else:

            if pred_c == 1:
                coef = random.uniform(0.85, 1.0)  # 1级：保留 85% ~ 100% 速度
            elif pred_c == 2:
                coef = random.uniform(0.55, 0.75)  # 2级：打折到 55% ~ 75%
            elif pred_c == 3:
                coef = random.uniform(0.25, 0.45)  # 3级：打折到 25% ~ 45%
            elif pred_c >= 4:
                coef = random.uniform(0.05, 0.15)  # 4级：极限龟速 5% ~ 15%
            else:
                coef = 1.0

            # 速度 = 自由流速度 × 折减系数
            v_new = free_flow[i] * coef

            v_new = max(0.0, min(v_new, free_flow[i]))

            # 流量 = Greenshields 物理模型公式
            if free_flow[i] > 0:
                speed_ratio = v_new / free_flow[i]
                q_new = jam_density[i] * v_new * (1 - speed_ratio)
            else:
                q_new = 0.0

            q_new = max(0.0, q_new)

        v_final = float(round(v_new, 2)) if not np.isnan(v_new) else 0.0
        q_final = float(round(q_new, 2)) if not np.isnan(q_new) else 0.0

        results.append({
            "node": int(i),
            "congestion": int(pred_c),
            "speed": v_final,
            "flow": q_final
        })

    return results


def single_step_simulation(t_start, node_embeddings, adjacency_matrix, p1, p2, p3, p4, modifiable_node, state_choice):
    seed_value = t_start
    if modifiable_node is not None: seed_value += int(modifiable_node) * 1000
    if state_choice is not None: seed_value += int(state_choice) * 10000
    np.random.seed(seed_value)
    random.seed(seed_value)

    current_flow, current_congestion, free_flow, jam_density = load_traffic_and_congestion_data(t_start)
    adj_modified = np.copy(adjacency_matrix)

    is_accident_active = False
    if modifiable_node is not None and state_choice is not None:
        if state_choice == 1:
            current_congestion[modifiable_node] = min(current_congestion[modifiable_node] + 1, 4)
        elif state_choice == 2:
            current_congestion[modifiable_node] = min(current_congestion[modifiable_node] + 2, 4)
        elif state_choice == 3:
            current_congestion[modifiable_node] = 4
            adj_modified[modifiable_node, :] = 0
            adj_modified[:, modifiable_node] = 0
            is_accident_active = True

    x_factors, y_factors = compute_factors(t_start, node_embeddings, current_flow, current_congestion, adj_modified)
    P_c, P_h = logistic_regression(x_factors, y_factors, p1, p2, p3, p4)

    next_congestion = update_congestion_index_dynamic(P_c, P_h, current_congestion, adj_modified, is_accident_active)

    if modifiable_node is not None and is_accident_active:
        next_congestion[modifiable_node] = 4

    predicted_step_metrics = simulate_traffic_metrics(
        next_congestion, free_flow, jam_density, modifiable_node, is_accident_active
    )

    return predicted_step_metrics


def parse_int_arg(arg, default=None):
    if arg is None or str(arg).lower() in ['null', 'none', 'undefined', '']: return default
    try:
        return int(arg)
    except ValueError:
        return default


if __name__ == "__main__":
    if len(sys.argv) >= 5:
        target_weekday = int(sys.argv[1])
        target_hour = int(sys.argv[2])
        target_minute = 0
        modifiable_node = parse_int_arg(sys.argv[3])
        state_choice = parse_int_arg(sys.argv[4])
    else:
        target_weekday = 3
        target_hour = 1
        target_minute = 0
        modifiable_node = 1
        state_choice = 1

    try:
        t_current = get_t_by_weekday_and_time(target_weekday, target_hour, target_minute)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)

    p1_opt = 0.010996524122214493
    p2_opt = -0.15631077615057787
    p3_opt = -0.8877787573556414
    p4_opt = -2.7686291943026453


    final_results = single_step_simulation(
        t_start=t_current,
        node_embeddings=node_embeddings,
        adjacency_matrix=adjacency_matrix,
        p1=p1_opt, p2=p2_opt, p3=p3_opt, p4=p4_opt,
        modifiable_node=modifiable_node,
        state_choice=state_choice
    )

    print(json.dumps(final_results, ensure_ascii=False))