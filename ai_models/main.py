import os
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# 导入我们刚才在 models 文件夹里写好的核心架构
from models.v_stgrn import V_STGRN

# ================= 1. 超参数设置 =================
SEQ_LEN = 12  # 输入历史 12 个时间步 (例如过去1小时的数据)
PRE_LEN = 12  # 预测未来 12 个时间步 (例如未来1小时的流量)
BATCH_SIZE = 32  # 批次大小 (每次喂给模型多少个样本)
HIDDEN_DIM = 64  # 模型隐藏层维度
NUM_HEADS = 4  # 时间保留网络 (RetNet) 的多头注意力头数
EPOCHS = 100  # 训练轮数 (为了快速测试，我们先设为10轮)
LEARNING_RATE = 0.001

# 自动检测是否可以使用 GPU 加速计算
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"当前使用的计算设备: {DEVICE}")


# ================= 2. 数据加载与预处理 =================
def load_and_preprocess_data():
    print("正在加载训练数据...")

    # 自动获取项目根目录路径，确保能准确找到 data 文件夹
    current_dir = os.path.dirname(os.path.abspath(__file__))
    traffic_path = os.path.join(current_dir, 'data', 'mock_traffic_data.npy')
    knn_path = os.path.join(current_dir, 'data', 'knn_adj.npy')
    dtw_path = os.path.join(current_dir, 'data', 'dtw_adj.npy')

    # 读取你历经千辛万苦生成的三大数据集
    traffic_data = np.load(traffic_path)  # 形状: (桥梁节点数, 总时间步)
    adj_knn = np.load(knn_path)  # KNN 空间拓扑图
    adj_dtw = np.load(dtw_path)  # DTW 语义关联图

    num_nodes, total_steps = traffic_data.shape

    # 模型设计需要融合三张图，这里用单位矩阵作为“物理距离图”的占位符
    adj_phys = np.eye(num_nodes)

    # --- Z-Score 数据归一化 (深度学习收敛必备，将数值压缩到0附近) ---
    mean_val = np.mean(traffic_data)
    std_val = np.std(traffic_data)
    traffic_data = (traffic_data - mean_val) / std_val

    # 转换矩阵形状，方便后续按照时间轴切片: 变为 (总时间步, 桥梁节点数)
    traffic_data = traffic_data.T

    # --- 构建滑动窗口 (Sliding Window) 制作监督学习样本 ---
    # 举例：用第 [0~11] 分钟预测 [12~23] 分钟，然后窗口滑动，用 [1~12] 预测 [13~24]...
    X, Y = [], []
    for i in range(total_steps - SEQ_LEN - PRE_LEN):
        X.append(traffic_data[i: i + SEQ_LEN, :])
        Y.append(traffic_data[i + SEQ_LEN: i + SEQ_LEN + PRE_LEN, :])

    X = np.array(X)
    Y = np.array(Y)

    # 增加一个特征维度，适应深度学习模型输入格式: (样本数, 时间步长, 节点数, 特征数)
    X = np.expand_dims(X, axis=-1)
    Y = np.expand_dims(Y, axis=-1)

    print(f"✅ 滑动窗口构建完成！共生成训练样本数: {X.shape[0]} 个")
    return X, Y, adj_phys, adj_knn, adj_dtw, mean_val, std_val


# ================= 3. 核心模型训练流程 =================
def train():
    # 1. 获取预处理好的数据
    X, Y, adj_phys, adj_knn, adj_dtw, mean_val, std_val = load_and_preprocess_data()
    num_nodes = X.shape[2]
    in_dim = X.shape[3]
    out_dim = Y.shape[3]

    # 2. 将 Numpy 数组转换为 PyTorch 专用的 Tensor 张量，并载入计算设备
    X_tensor = torch.FloatTensor(X).to(DEVICE)
    Y_tensor = torch.FloatTensor(Y).to(DEVICE)
    adj_phys_t = torch.FloatTensor(adj_phys).to(DEVICE)
    adj_knn_t = torch.FloatTensor(adj_knn).to(DEVICE)
    adj_dtw_t = torch.FloatTensor(adj_dtw).to(DEVICE)

    # 3. 构建数据加载器 (分批次打包数据送入模型，防止内存撑爆)
    dataset = TensorDataset(X_tensor, Y_tensor)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    # 4. 初始化我们精心设计的 V-STGRN 模型
    model = V_STGRN(num_nodes=num_nodes, in_dim=in_dim, hidden_dim=HIDDEN_DIM,
                    out_dim=out_dim, seq_len=SEQ_LEN, pre_len=PRE_LEN, num_heads=NUM_HEADS).to(DEVICE)

    # 5. 定义损失函数与优化器
    # 使用 Huber Loss，它对交通流中的突发异常值（如突然交通事故造成的拥堵）容忍度更高
    criterion = nn.HuberLoss(delta=1.0)
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4)

    print("\n🚀 开始训练 V-STGRN 模型...")
    model.train()  # 开启训练模式

    # 6. 开始 Epoch 循环迭代训练
    for epoch in range(EPOCHS):
        total_loss = 0.0
        for batch_x, batch_y in dataloader:
            optimizer.zero_grad()  # 清空上一轮的梯度

            # 前向传播：把历史流量和三张拓扑图喂给模型，得出预测结果
            preds = model(batch_x, adj_phys_t, adj_knn_t, adj_dtw_t)

            # 计算预测值与真实值之间的误差 (Loss)
            loss = criterion(preds, batch_y)

            # 反向传播，更新模型权重
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        # 打印当前 Epoch 的平均误差
        avg_loss = total_loss / len(dataloader)
        print(f"Epoch [{epoch + 1}/{EPOCHS}] | Average Loss: {avg_loss:.4f}")

    print("\n🎉 恭喜！模型训练圆满完成！")

    # 7. 保存训练好的模型“大脑”权重，方便日后直接调用预测，不用重新训练
    os.makedirs("checkpoints", exist_ok=True)
    torch.save(model.state_dict(), "checkpoints/v_stgrn_best.pth")
    print("💾 模型参数已成功保存至 checkpoints/v_stgrn_best.pth")


if __name__ == "__main__":
    train()