import torch
import torch.nn as nn
from .spatial_module import MultiGraphSpatialModule
from .temporal_module import MultiScaleRetention


class V_STGRN(nn.Module):
    def __init__(self, num_nodes, in_dim, hidden_dim, out_dim, seq_len, pre_len, num_heads):
        super().__init__()
        self.num_nodes = num_nodes
        self.seq_len = seq_len
        self.pre_len = pre_len
        self.hidden_dim = hidden_dim

        # 将 4 维特征映射为高维隐藏层 (in_dim=4, hidden_dim=64)
        self.input_proj = nn.Linear(in_dim, hidden_dim)

        # 传入空间模块时已经是 hidden_dim 维度
        self.spatial_module = MultiGraphSpatialModule(hidden_dim)

        self.temporal_module = MultiScaleRetention(hidden_dim, num_heads)

        # 最终映射为输出维度 (只输出 flow 一维特征)
        self.output_proj = nn.Sequential(
            nn.Linear(seq_len * hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, pre_len * out_dim)
        )

    def forward(self, x, adj_acc, adj_dtw):
        batch_size = x.size(0)

        # [batch_size, seq_len, num_nodes, in_dim] -> [batch_size, seq_len, num_nodes, hidden_dim]
        x = self.input_proj(x)

        x_spatial_in = x.view(batch_size * self.seq_len, self.num_nodes, self.hidden_dim)
        x_spatial_out = self.spatial_module(x_spatial_in, adj_acc, adj_dtw)

        x_temporal_in = x_spatial_out.view(batch_size, self.seq_len, self.num_nodes, self.hidden_dim)
        x_temporal_in = x_temporal_in.permute(0, 2, 1, 3).contiguous().view(
            batch_size * self.num_nodes, self.seq_len, self.hidden_dim
        )
        x_temporal_out = self.temporal_module(x_temporal_in)

        x_out_in = x_temporal_out.view(batch_size * self.num_nodes, -1)
        preds = self.output_proj(x_out_in)

        preds = preds.view(batch_size, self.num_nodes, self.pre_len, -1).permute(0, 2, 1, 3).contiguous()

        return preds