import os
import sys
import json
import glob
import re
import numpy as np
import pandas as pd
import torch
from datetime import datetime, timedelta

from models.v_stgrn import V_STGRN


# ================= 0. 辅助函数与日志 =================
def log_info(message):
    """日志重定向到 stderr，防止污染输出给前端的 JSON 数据"""
    print(message, file=sys.stderr)


# ================= 1. 基础配置 =================
SEQ_LEN = 12
PRE_LEN = 12
HIDDEN_DIM = 64
NUM_HEADS = 4
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "shanghai_data", "mock_data")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
BEST_MODEL_PATH = os.path.join(RESULTS_DIR, "checkpoints", "v_stgrn_best.pth")

ACC_PATH = os.path.join(BASE_DIR, "shanghai_data", "generate_acc_shanghai", "link_matrix_shanghai.csv")
DTW_PATH = os.path.join(BASE_DIR, "shanghai_data", "generate_dtw_shanghai", "dtw_adj_shanghai.csv")


def get_congestion_level(flow):
    if flow < 600:
        return "GREEN"
    elif flow < 1200:
        return "YELLOW"
    else:
        return "RED"


def normalize_adj(adj):
    adj = adj + np.eye(adj.shape[0])
    rowsum = np.array(adj.sum(1))
    d_inv_sqrt = np.power(rowsum, -0.5).flatten()
    d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.
    d_mat_inv_sqrt = np.diag(d_inv_sqrt)
    return adj.dot(d_mat_inv_sqrt).transpose().dot(d_mat_inv_sqrt)


# ================= 2. 时间戳精准查找 =================
def get_t_by_weekday_and_time(target_weekday, target_hour, all_timestamps):
    pd_weekday = target_weekday - 1
    target_minute = 0

    # 1. 计算总样本数和测试集切分点 (与训练脚本保持绝对一致)
    total_samples = len(all_timestamps) - SEQ_LEN - PRE_LEN + 1
    val_idx = int(total_samples * 0.80)

    # 2. 测试集在原始时间轴上的真实起点与终点索引
    test_start_real_idx = val_idx + SEQ_LEN
    test_end_real_idx = len(all_timestamps) - PRE_LEN

    matches = np.where((all_timestamps.dayofweek == pd_weekday) &
                       (all_timestamps.hour == target_hour) &
                       (all_timestamps.minute == target_minute))[0]

    # 3. 过滤出只属于【纯测试集】范围内的时间点
    valid_matches = [idx for idx in matches if test_start_real_idx <= idx <= test_end_real_idx]

    if len(valid_matches) == 0:
        real_start = all_timestamps[test_start_real_idx]
        real_end = all_timestamps[test_end_real_idx]
        raise ValueError(
            f"\n\n❌ 查找失败！您请求的时间不在模型【未见过的测试集】范围内。\n"
            f"根据严格的数据集 80% 划分规则，当前可用的纯测试集时间段为：\n"
            f"🟢 起点: {real_start.strftime('%Y-%m-%d %H:%M')} (星期{real_start.dayofweek + 1})\n"
            f"🔴 终点: {real_end.strftime('%Y-%m-%d %H:%M')} (星期{real_end.dayofweek + 1})\n"
            f"请挑选上述时间段内的一个整点进行测试！"
        )

    return valid_matches[0], all_timestamps[valid_matches[0]]


# ================= 3. 核心推理管线 =================
def run_inference(target_weekday, target_hour):
    if not os.path.exists(BEST_MODEL_PATH):
        raise FileNotFoundError(f"找不到模型权重 {BEST_MODEL_PATH}")

    # ================= A. 加载并构建全局序列 =================
    log_info("📂 正在扫描并加载历史特征矩阵...")
    files = glob.glob(os.path.join(DATA_DIR, "shanghaidata_*.xlsx"))
    files.sort(key=lambda x: int(re.search(r'shanghaidata_(\d+)', os.path.basename(x)).group(1)))

    if not files:
        raise FileNotFoundError("找不到 Excel 数据文件")

    traffic_sequence = []
    timestamps_list = []

    for file in files:
        df = pd.read_excel(file).sort_values(by='node')
        ts = pd.to_datetime(df['timestamp'].iloc[0])
        timestamps_list.append(ts)

        numeric_feats = df[['flow', 'poi', 'speed', 'congestion']].fillna(0).values
        times = pd.to_datetime(df['timestamp']).dt.floor('30min')
        time_norm = ((times.dt.hour * 60 + times.dt.minute) / 1440.0).values.reshape(-1, 1)
        traffic_sequence.append(np.concatenate([numeric_feats, time_norm], axis=-1))

    all_timestamps = pd.DatetimeIndex(timestamps_list).floor('30min')

    # ================= B. 时间定位 =================
    target_idx, base_datetime = get_t_by_weekday_and_time(
        target_weekday, target_hour, all_timestamps
    )
    log_info(f"🎯 成功锁定时间: {base_datetime.strftime('%Y-%m-%d %H:%M')}")

    # ================= C. 数据标准化与切片 =================
    traffic_data = np.array(traffic_sequence).transpose(1, 0, 2)
    mean_val = np.mean(traffic_data, axis=1, keepdims=True)
    std_val = np.std(traffic_data, axis=1, keepdims=True)
    std_val[std_val < 1e-5] = 1.0

    mean_inv = mean_val[:, :, 0].reshape(1, 1, -1, 1)
    std_inv = std_val[:, :, 0].reshape(1, 1, -1, 1)

    traffic_data_norm = (traffic_data - mean_val) / std_val
    traffic_data_norm[:, :, 4] = traffic_data[:, :, 4]
    traffic_data_norm = traffic_data_norm.transpose(1, 0, 2)

    custom_input = traffic_data_norm[target_idx - SEQ_LEN: target_idx, :, :]
    custom_input = np.expand_dims(custom_input, 0)

    # 加载拓扑图
    df_acc = pd.read_csv(ACC_PATH, index_col=0)
    df_dtw = pd.read_csv(DTW_PATH, index_col=0)
    adj_acc = normalize_adj(df_acc.values.astype(np.float32))
    adj_dtw = normalize_adj(df_dtw.values.astype(np.float32))
    num_nodes = adj_acc.shape[0]

    # ================= D. 模型前向推演 =================
    log_info(f"🧠 加载模型推演中...")
    model = V_STGRN(num_nodes, 5, HIDDEN_DIM, 1, SEQ_LEN, PRE_LEN, NUM_HEADS).to(DEVICE)
    model.load_state_dict(torch.load(BEST_MODEL_PATH, map_location=DEVICE))
    model.eval()

    with torch.no_grad():
        input_t = torch.FloatTensor(custom_input).to(DEVICE)
        future_preds = model(input_t, torch.FloatTensor(adj_acc).to(DEVICE),
                             torch.FloatTensor(adj_dtw).to(DEVICE)).cpu().numpy()

    future_preds_real = np.maximum(future_preds * std_inv + mean_inv, 0).squeeze()
    history_real = (custom_input.squeeze()[:, :, 0] * std_inv.squeeze()) + mean_inv.squeeze()

    # ================= E. JSON 封装 =================
    np.random.seed(42)
    mock_lngs = np.random.uniform(121.3, 121.6, num_nodes)
    mock_lats = np.random.uniform(31.1, 31.4, num_nodes)
    node_names = [f"Node_{i}" for i in range(num_nodes)]

    map_data_steps = []
    for step in range(PRE_LEN):
        step_time = (base_datetime + timedelta(minutes=30 * (step + 1))).strftime("%Y-%m-%d %H:%M:%S")
        step_nodes = []
        for i in range(num_nodes):
            pred_flow = float(future_preds_real[step, i])
            step_nodes.append({
                "node_id": node_names[i],
                "lng": float(mock_lngs[i]),
                "lat": float(mock_lats[i]),
                "flow_pred": round(pred_flow, 1),
                "congestion_level": get_congestion_level(pred_flow)
            })
        map_data_steps.append({
            "step_index": step + 1,
            "forecast_time": step_time,
            "nodes": step_nodes
        })

    x_axis_times = [(base_datetime + timedelta(minutes=30 * step)).strftime("%H:%M") for step in
                    range(-SEQ_LEN + 1, PRE_LEN + 1)]
    chart_data_list = []
    for i in range(num_nodes):
        hist_flows = [round(float(val), 1) for val in history_real[:, i]]
        pred_flows = [round(float(val), 1) for val in future_preds_real[:, i]]
        chart_data_list.append({
            "node_id": node_names[i],
            "x_axis_times": x_axis_times,
            "series": {
                "history_data": hist_flows + [None] * PRE_LEN,
                "forecast_data": [None] * (SEQ_LEN - 1) + [hist_flows[-1]] + pred_flows
            }
        })

    final_output = {
        "status": "success",
        "map_data": {
            "base_timestamp": base_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "total_steps": PRE_LEN,
            "data": map_data_steps
        },
        "chart_data": chart_data_list
    }

    map_json_path = os.path.join(RESULTS_DIR, "frontend_map_data.json")
    chart_json_path = os.path.join(RESULTS_DIR, "frontend_chart_data.json")

    with open(map_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_output["map_data"], f, ensure_ascii=False, indent=2)

    with open(chart_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_output["chart_data"], f, ensure_ascii=False, indent=2)

    log_info(f"💾 测试 JSON 文件已保存至 {RESULTS_DIR} 目录下")
    print(json.dumps(final_output, ensure_ascii=False))


# ================= 4. 主程序入口 =================
if __name__ == "__main__":
    if len(sys.argv) >= 3:
        target_weekday = int(sys.argv[1])
        target_hour = int(sys.argv[2])
        log_info(f"👉 收到前端参数: 星期{target_weekday} {target_hour}:00")
    else:
        target_weekday = 1
        target_hour = 12
        log_info("👉 未收到参数，尝试测试 星期1 12:00")

    try:
        run_inference(target_weekday, target_hour)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)