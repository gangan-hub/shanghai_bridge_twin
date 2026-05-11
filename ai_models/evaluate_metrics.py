import os
import numpy as np
import torch
import pandas as pd

# 导入核心模型
from models.v_stgrn import V_STGRN

# ================= 1. 超参数设置 (必须与训练时完全一致) =================
SEQ_LEN = 12
PRE_LEN = 12
HIDDEN_DIM = 64
NUM_HEADS = 4
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def calculate_metrics():
    print("正在加载数据与模型以计算全局评估指标...")

    # ================= 2. 加载数据 =================
    current_dir = os.path.dirname(os.path.abspath(__file__))
    traffic_data = np.load(os.path.join(current_dir, 'data', 'mock_traffic_data.npy'))
    adj_knn = np.load(os.path.join(current_dir, 'data', 'knn_adj.npy'))
    adj_dtw = np.load(os.path.join(current_dir, 'data', 'dtw_adj.npy'))

    num_nodes = traffic_data.shape[0]
    adj_phys = np.eye(num_nodes)

    mean_val = np.mean(traffic_data)
    std_val = np.std(traffic_data)

    # 抽取最后 24 个时间步进行测试
    test_seq = traffic_data[:, -24:]

    # 仅对输入数据进行归一化
    test_seq_norm = (test_seq - mean_val) / std_val
    X = test_seq_norm[:, :SEQ_LEN].T

    # Y_true 是全部节点在未来 12 步的真实流量：形状 (Pre_Len, Num_Nodes)
    Y_true = test_seq[:, SEQ_LEN:].T

    X_tensor = torch.FloatTensor(X).unsqueeze(0).unsqueeze(-1).to(DEVICE)
    adj_phys_t = torch.FloatTensor(adj_phys).to(DEVICE)
    adj_knn_t = torch.FloatTensor(adj_knn).to(DEVICE)
    adj_dtw_t = torch.FloatTensor(adj_dtw).to(DEVICE)

    # ================= 3. 加载模型预测 =================
    model = V_STGRN(num_nodes=num_nodes, in_dim=1, hidden_dim=HIDDEN_DIM,
                    out_dim=1, seq_len=SEQ_LEN, pre_len=PRE_LEN, num_heads=NUM_HEADS).to(DEVICE)

    model.load_state_dict(torch.load("checkpoints/v_stgrn_best.pth", map_location=DEVICE))
    model.eval()

    with torch.no_grad():
        preds = model(X_tensor, adj_phys_t, adj_knn_t, adj_dtw_t)

    # ================= 4. 反归一化 =================
    preds_np = preds.squeeze().cpu().numpy()
    preds_real = (preds_np * std_val) + mean_val
    preds_real = np.maximum(0, preds_real)  # 交通流不为负数

    # ================= 5. 计算三大核心指标 =================
    # MAE (Mean Absolute Error) - 平均绝对误差
    mae = np.mean(np.abs(preds_real - Y_true))

    # RMSE (Root Mean Square Error) - 均方根误差
    rmse = np.sqrt(np.mean(np.square(preds_real - Y_true)))

    # MAPE (Mean Absolute Percentage Error) - 平均绝对百分比误差
    # 忽略真实值为0的点以避免除以0的错误
    mask = Y_true > 1e-5
    mape = np.mean(np.abs((Y_true[mask] - preds_real[mask]) / Y_true[mask])) * 100

    # ================= 6. 打印论文格式的表格 =================
    print("\n" + "=" * 50)
    print("🌟 V-STGRN 全局路网预测性能评估报告 🌟")
    print("=" * 50)

    metrics_df = pd.DataFrame({
        "评估指标 (Metrics)": ["MAE (平均绝对误差)", "RMSE (均方根误差)", "MAPE (平均绝对百分比误差)"],
        "数值 (Value)": [f"{mae:.4f}", f"{rmse:.4f}", f"{mape:.2f}%"],
        "物理含义": [
            "预测流量与真实流量的平均绝对车辆差级。",
            "对异常大误差更敏感，衡量模型预测的稳定性。",
            "预测误差占真实流量的平均百分比比例。"
        ]
    })

    # 格式化输出表格
    print(metrics_df.to_string(index=False))
    print("=" * 50)



if __name__ == "__main__":
    calculate_metrics()