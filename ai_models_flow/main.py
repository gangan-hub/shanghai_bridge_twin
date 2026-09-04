import os
import glob
import re
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import matplotlib.pyplot as plt
from models.v_stgrn import V_STGRN

# ================= 1. 全局配置与超参数 =================
SEQ_LEN = 12
PRE_LEN = 12
BATCH_SIZE = 16
HIDDEN_DIM = 64
NUM_HEADS = 4
EPOCHS = 100
LEARNING_RATE = 0.001
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 👇 升级为绝对路径动态拼接（告别运行目录报错问题）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "shanghai_data", "mock_data")
DTW_PATH = os.path.join(BASE_DIR, "shanghai_data", "generate_dtw_shanghai", "dtw_adj_shanghai.csv")
ACC_PATH = os.path.join(BASE_DIR, "shanghai_data", "generate_acc_shanghai", "link_matrix_shanghai.csv")
RESULTS_DIR = os.path.join(BASE_DIR, "results")
BEST_MODEL_PATH = os.path.join(RESULTS_DIR, "checkpoints", "v_stgrn_best.pth")

COLOR_BG, COLOR_TEXT, COLOR_TRUTH, COLOR_PRED, COLOR_FUTURE = '#080c15', '#ffffff', '#00ffcc', '#ff0055', '#0088ff'

# ================= 2. 辅助函数 =================
def normalize_adj(adj):
    adj = adj + np.eye(adj.shape[0])
    rowsum = np.array(adj.sum(1))
    d_inv_sqrt = np.power(rowsum, -0.5).flatten()
    d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.
    d_mat_inv_sqrt = np.diag(d_inv_sqrt)
    return adj.dot(d_mat_inv_sqrt).transpose().dot(d_mat_inv_sqrt)


def masked_mape(y_true, y_pred, null_val=1.0):
    with np.errstate(divide='ignore', invalid='ignore'):
        mask = y_true >= null_val
        mape = np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])
        return np.mean(mape) * 100


def calculate_metrics(y_true, y_pred):
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean(np.square(y_true - y_pred)))
    mape = masked_mape(y_true, y_pred)
    return mae, rmse, mape


def _format_ax(ax):
    ax.tick_params(axis='x', colors=COLOR_TEXT)
    ax.tick_params(axis='y', colors=COLOR_TEXT)
    for spine in ax.spines.values(): spine.set_color('#334455')
    ax.grid(True, color='#1a2535', linestyle='-.', alpha=0.7)


# ================= 3. 数据加载 (带精准时间戳切分) =================
def load_all_data():
    print("📂 正在加载双核拓扑与 5 维多源特征数据...")
    df_acc = pd.read_csv(ACC_PATH, index_col=0)
    df_dtw = pd.read_csv(DTW_PATH, index_col=0)

    adj_acc = normalize_adj(df_acc.values.astype(np.float32))
    adj_dtw = normalize_adj(df_dtw.values.astype(np.float32))

    files = glob.glob(os.path.join(DATA_DIR, "shanghaidata_*.xlsx"))
    files.sort(key=lambda x: int(re.search(r'shanghaidata_(\d+)', os.path.basename(x)).group(1)))

    traffic_sequence = []
    timestamps_list = []

    for file in files:
        df = pd.read_excel(file).sort_values(by='node')

        # 提取每个文件的时间戳并记录
        ts = pd.to_datetime(df['timestamp'].iloc[0])
        timestamps_list.append(ts)

        numeric_feats = df[['flow', 'poi', 'speed', 'congestion']].interpolate(method='linear',
                                                                               limit_direction='both').fillna(0).values

        times = pd.to_datetime(df['timestamp'])
        time_norm = ((times.dt.hour * 60 + times.dt.minute) / 1440.0).values.reshape(-1, 1)

        combined_feats = np.concatenate([numeric_feats, time_norm], axis=-1)
        traffic_sequence.append(combined_feats)

    # 构建全局对齐时间轴
    all_timestamps = pd.DatetimeIndex(timestamps_list).floor('30min')
    traffic_data = np.array(traffic_sequence).transpose(1, 0, 2)

    mean_val = np.mean(traffic_data, axis=1, keepdims=True)
    std_val = np.std(traffic_data, axis=1, keepdims=True)
    std_val[std_val < 1e-5] = 1.0

    traffic_data_norm = (traffic_data - mean_val) / std_val
    traffic_data_norm[:, :, 4] = traffic_data[:, :, 4]
    traffic_data_norm = traffic_data_norm.transpose(1, 0, 2)

    X, Y = [], []
    # 修正总样本数计算
    total_samples = traffic_data_norm.shape[0] - SEQ_LEN - PRE_LEN + 1

    for i in range(total_samples):
        X.append(traffic_data_norm[i: i + SEQ_LEN, :, :])
        Y.append(traffic_data_norm[i + SEQ_LEN: i + SEQ_LEN + PRE_LEN, :, 0:1])

    X = np.array(X)
    Y = np.array(Y)

    train_idx = int(total_samples * 0.70)
    val_idx = int(total_samples * 0.80)

    X_train, Y_train = X[:train_idx], Y[:train_idx]
    X_val, Y_val = X[train_idx:val_idx], Y[train_idx:val_idx]
    X_test, Y_test = X[val_idx:], Y[val_idx:]

    # 打印准确的数据集时间划分范围
    print("\n" + "=" * 65)
    print("📊 数据集时间段严格划分结果 (基于预测目标时间)：")
    print(
        f"🟢 训练集 (Train) 70%: {all_timestamps[SEQ_LEN].strftime('%m-%d %H:%M')} 到 {all_timestamps[SEQ_LEN + train_idx - 1].strftime('%m-%d %H:%M')}")
    print(
        f"🟡 验证集 (Val)   10%: {all_timestamps[SEQ_LEN + train_idx].strftime('%m-%d %H:%M')} 到 {all_timestamps[SEQ_LEN + val_idx - 1].strftime('%m-%d %H:%M')}")
    print(
        f"🔴 测试集 (Test)  20%: {all_timestamps[SEQ_LEN + val_idx].strftime('%m-%d %H:%M')} 到 {all_timestamps[-1].strftime('%m-%d %H:%M')}")
    print("=" * 65 + "\n")

    latest_input = traffic_data_norm[-SEQ_LEN:, :, :]
    latest_input = np.expand_dims(latest_input, 0)

    mean_inv = mean_val[:, :, 0].reshape(1, 1, -1, 1)
    std_inv = std_val[:, :, 0].reshape(1, 1, -1, 1)

    return (X_train, Y_train, X_val, Y_val, X_test, Y_test,
            latest_input, adj_acc, adj_dtw, mean_inv, std_inv)


# ================= 4. 管线执行 =================
def run_full_pipeline():
    print("=" * 65)
    print("🚀 启动 V-STGRN 一体化管线 (5维特征聚合 + 深度残差图版)")
    print("=" * 65)

    os.makedirs(os.path.join(RESULTS_DIR, "checkpoints"), exist_ok=True)

    (X_train, Y_train, X_val, Y_val, X_test, Y_test,
     latest_input, adj_acc, adj_dtw, mean_inv, std_inv) = load_all_data()

    num_nodes = adj_acc.shape[0]
    in_dim = 5
    out_dim = 1

    adj_acc_t = torch.FloatTensor(adj_acc).to(DEVICE)
    adj_dtw_t = torch.FloatTensor(adj_dtw).to(DEVICE)

    train_loader = DataLoader(TensorDataset(torch.FloatTensor(X_train).to(DEVICE),
                                            torch.FloatTensor(Y_train).to(DEVICE)),
                              batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(TensorDataset(torch.FloatTensor(X_val).to(DEVICE),
                                          torch.FloatTensor(Y_val).to(DEVICE)),
                            batch_size=BATCH_SIZE, shuffle=False)

    model = V_STGRN(num_nodes, in_dim, HIDDEN_DIM, out_dim, SEQ_LEN, PRE_LEN, NUM_HEADS).to(DEVICE)
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.SmoothL1Loss(beta=1.0)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5)

    best_val_loss = float('inf')

    print(f"\n🔥 阶段 1/4: 开始训练 (Epochs: {EPOCHS}, Device: {DEVICE})...")
    for epoch in range(EPOCHS):
        model.train()
        train_loss = 0.0
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            preds = model(batch_x, adj_acc_t, adj_dtw_t)
            loss = criterion(preds, batch_y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                preds = model(batch_x, adj_acc_t, adj_dtw_t)
                loss = criterion(preds, batch_y)
                val_loss += loss.item()

        avg_train = train_loss / len(train_loader)
        avg_val = val_loss / len(val_loader)
        scheduler.step(avg_val)

        if avg_val < best_val_loss:
            best_val_loss = avg_val
            torch.save(model.state_dict(), BEST_MODEL_PATH)
            mark = "⭐"
        else:
            mark = ""

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(
                f"   -> Epoch [{epoch + 1:03d}/{EPOCHS}] | Train Loss: {avg_train:.4f} | Val Loss: {avg_val:.4f} {mark}")

    print("\n🔍 阶段 2/4: 在封存测试集上评估精度...")
    model.load_state_dict(torch.load(BEST_MODEL_PATH, map_location=DEVICE, weights_only=True))
    model.eval()

    test_loader = DataLoader(TensorDataset(torch.FloatTensor(X_test).to(DEVICE),
                                           torch.FloatTensor(Y_test).to(DEVICE)),
                             batch_size=BATCH_SIZE, shuffle=False)

    test_preds_list, test_truths_list = [], []
    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            test_preds_list.append(model(batch_x, adj_acc_t, adj_dtw_t).cpu().numpy())
            test_truths_list.append(batch_y.cpu().numpy())

    test_preds = np.concatenate(test_preds_list, axis=0)
    test_truths = np.concatenate(test_truths_list, axis=0)

    test_preds_real = np.maximum(test_preds * std_inv + mean_inv, 0)
    test_truths_real = np.where((test_truths * std_inv + mean_inv) < 1.0, 0.0, (test_truths * std_inv + mean_inv))
    test_preds_real = np.where(test_preds_real < 1.0, 0.0, test_preds_real)

    mae, rmse, mape = calculate_metrics(test_truths_real, test_preds_real)
    print(f"   📊 [评估结果] MAE: {mae:.2f} 辆 | RMSE: {rmse:.2f} 辆 | MAPE: {mape:.2f}%")

    print("\n🔮 阶段 3/4: 注入最新业务流数据推演...")
    with torch.no_grad():
        future_preds = model(torch.FloatTensor(latest_input).to(DEVICE), adj_acc_t, adj_dtw_t).cpu().numpy()
    future_preds_real = np.maximum(future_preds * std_inv + mean_inv, 0).squeeze()

    print("\n🎨 阶段 4/4: 渲染分析看板...")
    fig = plt.figure(figsize=(24, 8), facecolor=COLOR_BG)
    node_idx, step_idx = 0, 0

    ax1 = plt.subplot(1, 3, 1)
    ax1.set_facecolor(COLOR_BG)
    plot_len = min(80, test_preds_real.shape[0])
    ax1.plot(test_truths_real[:plot_len, step_idx, node_idx, 0], color=COLOR_TRUTH, label='Ground Truth', linewidth=2)
    ax1.plot(test_preds_real[:plot_len, step_idx, node_idx, 0], color=COLOR_PRED, label='Predicted', linestyle='--',
             linewidth=2)
    ax1.set_title("Test Set: Sequence Fit Verification", color=COLOR_TEXT, fontsize=16)
    ax1.legend(facecolor='#111825', edgecolor='#334455', labelcolor=COLOR_TEXT)
    _format_ax(ax1)

    ax2 = plt.subplot(1, 3, 2)
    ax2.set_facecolor(COLOR_BG)
    ax2.scatter(test_truths_real[:, step_idx, node_idx, 0], test_preds_real[:, step_idx, node_idx, 0],
                color=COLOR_TRUTH, alpha=0.3, s=15)
    ax2.plot([0, test_truths_real[:, step_idx, node_idx, 0].max()],
             [0, test_truths_real[:, step_idx, node_idx, 0].max()], color=COLOR_PRED, linestyle='--')
    ax2.set_title(f"Correlation: MAE={mae:.1f} | MAPE={mape:.1f}%", color=COLOR_TEXT, fontsize=16)
    _format_ax(ax2)

    ax3 = plt.subplot(1, 3, 3)
    ax3.set_facecolor(COLOR_BG)
    past_history = (latest_input.squeeze()[:, node_idx, 0] * std_inv.squeeze()[node_idx]) + mean_inv.squeeze()[node_idx]
    future_forecast = future_preds_real[:, node_idx]

    ax3.plot(range(1, SEQ_LEN + 1), past_history, color=COLOR_TRUTH, marker='o', label='Past 6 Hours', linewidth=2)
    ax3.plot(range(SEQ_LEN, SEQ_LEN + PRE_LEN + 1), np.insert(future_forecast, 0, past_history[-1]), color=COLOR_FUTURE,
             marker='X', linestyle='-.', label='Forecast Next 6 Hours', linewidth=2.5)
    ax3.set_title(f"Real-Time Forecast (Node {node_idx})", color=COLOR_TEXT, fontsize=16)
    ax3.axvline(x=SEQ_LEN, color='#556677', linestyle='--')
    ax3.legend(facecolor='#111825', edgecolor='#334455', labelcolor=COLOR_TEXT)
    _format_ax(ax3)

    plt.tight_layout(pad=3.0)
    plt.savefig(os.path.join(RESULTS_DIR, "v_stgrn_full_dashboard.png"), dpi=300, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close()


if __name__ == "__main__":
    run_full_pipeline()