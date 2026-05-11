import os
import numpy as np
import torch
import matplotlib.pyplot as plt

# 导入我们的核心模型
from models.v_stgrn import V_STGRN

# ================= 1. 保持与训练时一致的超参数 =================
SEQ_LEN = 12
PRE_LEN = 12
HIDDEN_DIM = 64
NUM_HEADS = 4
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def evaluate_and_plot():
    print("正在加载测试数据与模型大脑...")

    # ================= 2. 加载数据 =================
    current_dir = os.path.dirname(os.path.abspath(__file__))
    traffic_data = np.load(os.path.join(current_dir, 'data', 'mock_traffic_data.npy'))
    adj_knn = np.load(os.path.join(current_dir, 'data', 'knn_adj.npy'))
    adj_dtw = np.load(os.path.join(current_dir, 'data', 'dtw_adj.npy'))

    num_nodes = traffic_data.shape[0]
    adj_phys = np.eye(num_nodes)

    # 提取均值和标准差 (用于后续的反归一化还原)
    mean_val = np.mean(traffic_data)
    std_val = np.std(traffic_data)

    # 我们抽取数据集中最后 24 个时间步（约2小时）作为“未见过的未来测试集”
    # 前 12 个时间步作为输入 X，后 12 个时间步作为真实的参考答案 Y
    test_seq = traffic_data[:, -24:]

    # 仅对输入数据进行归一化
    test_seq_norm = (test_seq - mean_val) / std_val
    X = test_seq_norm[:, :SEQ_LEN].T  # 形状变回 (Seq_Len, Num_Nodes)
    Y_true = test_seq[:, SEQ_LEN:].T  # 真实的流量原始值，留着画图对比用

    # 增加深度学习所需的 Batch 和 Feature 维度
    X_tensor = torch.FloatTensor(X).unsqueeze(0).unsqueeze(-1).to(DEVICE)
    adj_phys_t = torch.FloatTensor(adj_phys).to(DEVICE)
    adj_knn_t = torch.FloatTensor(adj_knn).to(DEVICE)
    adj_dtw_t = torch.FloatTensor(adj_dtw).to(DEVICE)

    # ================= 3. 加载模型并进行预测 =================
    model = V_STGRN(num_nodes=num_nodes, in_dim=1, hidden_dim=HIDDEN_DIM,
                    out_dim=1, seq_len=SEQ_LEN, pre_len=PRE_LEN, num_heads=NUM_HEADS).to(DEVICE)

    # 加载刚才训练好的最优权重
    model.load_state_dict(torch.load("checkpoints/v_stgrn_best.pth", map_location=DEVICE))
    model.eval()  # 开启评估模式 (关闭 Dropout 等训练特有操作)

    print("🚀 正在让 V-STGRN 进行未来交通流预测...")
    with torch.no_grad():  # 测试阶段不需要计算梯度，节约显存
        preds = model(X_tensor, adj_phys_t, adj_knn_t, adj_dtw_t)

    # ================= 4. 数据反归一化 (还原为真实车流量) =================
    # 去掉多余的维度，变回 (Pre_Len, Num_Nodes)
    preds_np = preds.squeeze().cpu().numpy()
    # Z-Score 逆运算：真实值 = (预测值 * 标准差) + 均值
    preds_real = (preds_np * std_val) + mean_val
    # 强制修正：车流量不可能为负数
    preds_real = np.maximum(0, preds_real)

    # ================= 5. 绘制论文级对比折线图 =================
    # 我们可以随意挑选一个节点来看看效果，这里以“第0号桥梁节点”为例
    target_node = 0

    plt.figure(figsize=(10, 5))
    # 画出真实的交通流曲线（蓝色实线）
    plt.plot(range(1, PRE_LEN + 1), Y_true[:, target_node], label='Ground Truth (Real Flow)', marker='o',
             color='#1f77b4', linewidth=2)
    # 画出模型预测的交通流曲线（红色虚线）
    plt.plot(range(1, PRE_LEN + 1), preds_real[:, target_node], label='V-STGRN Prediction', marker='x', color='#d62728',
             linestyle='--', linewidth=2)

    plt.title(f"Shanghai Bridge Traffic Flow Prediction (Node ID: {target_node})", fontsize=14, pad=15)
    plt.xlabel("Future Time Steps (1 Step = 5 Mins)", fontsize=12)
    plt.ylabel("Traffic Flow (Vehicles)", fontsize=12)
    plt.legend(fontsize=12, loc='upper left')
    plt.grid(True, linestyle=':', alpha=0.7)

    # 去除多余留白
    plt.tight_layout()
    # 导出高清图片
    plt.savefig("prediction_vs_real.png", dpi=300)
    print("\n✅ 闭卷考试完成！")
    print("🎉 预测对比图已保存为项目目录下的: prediction_vs_real.png")


if __name__ == "__main__":
    evaluate_and_plot()