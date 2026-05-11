import torch
import torch.nn as nn
import torch.nn.functional as F


class GraphConvolution(nn.Module):
    """基础的空间图卷积层"""

    def __init__(self, in_features, out_features):
        super(GraphConvolution, self).__init__()
        self.weight = nn.Parameter(torch.FloatTensor(in_features, out_features))
        self.bias = nn.Parameter(torch.FloatTensor(out_features))
        nn.init.xavier_uniform_(self.weight)
        nn.init.zeros_(self.bias)

    def forward(self, x, adj):
        support = torch.matmul(x, self.weight)
        return torch.matmul(adj, support) + self.bias


class MultiGraphSpatialModule(nn.Module):
    """升级版双核空间图模块 (双层 GCN + 残差连接)"""

    # 此时进入模块的特征已经被上游线性层投影为 hidden_dim 维度
    def __init__(self, hidden_dim, dropout_rate=0.3):
        super().__init__()

        # 物理宇宙 (ACC) 的双层特征提取
        self.gcn_acc_1 = GraphConvolution(hidden_dim, hidden_dim)
        self.gcn_acc_2 = GraphConvolution(hidden_dim, hidden_dim)

        # 语义宇宙 (DTW) 的双层特征提取
        self.gcn_dtw_1 = GraphConvolution(hidden_dim, hidden_dim)
        self.gcn_dtw_2 = GraphConvolution(hidden_dim, hidden_dim)

        self.gate = nn.Linear(hidden_dim * 2, 2)
        self.dropout = nn.Dropout(dropout_rate)

    def forward(self, x, adj_acc, adj_dtw):
        # 引入残差特征，防止网络变深后梯度消失
        res = x

        # --- 分支 1: ACC 图网络提取 ---
        h_acc = F.relu(self.gcn_acc_1(x, adj_acc))
        h_acc = self.dropout(h_acc)
        h_acc = F.relu(self.gcn_acc_2(h_acc, adj_acc))
        h_acc = h_acc + res  # 残差相加

        # --- 分支 2: DTW 图网络提取 ---
        h_dtw = F.relu(self.gcn_dtw_1(x, adj_dtw))
        h_dtw = self.dropout(h_dtw)
        h_dtw = F.relu(self.gcn_dtw_2(h_dtw, adj_dtw))
        h_dtw = h_dtw + res  # 残差相加

        # --- 门控融合 ---
        h_concat = torch.cat([h_acc, h_dtw], dim=-1)
        gate_scores = F.softmax(self.gate(h_concat), dim=-1)

        alpha_acc = gate_scores[..., 0:1]
        alpha_dtw = gate_scores[..., 1:2]

        h_fused = (alpha_acc * h_acc) + (alpha_dtw * h_dtw)
        return h_fused