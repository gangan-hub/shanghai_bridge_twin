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

        self.input_proj = nn.Linear(in_dim, hidden_dim)
        self.spatial_module = MultiGraphSpatialModule(hidden_dim, hidden_dim)
        self.temporal_module = MultiScaleRetention(hidden_dim, num_heads)

        self.output_proj = nn.Sequential(
            nn.Linear(seq_len * hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, pre_len * out_dim)
        )

    def forward(self, x, adj_phys, adj_knn, adj_dtw):
        batch_size = x.size(0)
        x = self.input_proj(x)

        x_spatial_in = x.view(batch_size * self.seq_len, self.num_nodes, self.hidden_dim)
        x_spatial_out = self.spatial_module(x_spatial_in, adj_phys, adj_knn, adj_dtw)

        x_temporal_in = x_spatial_out.view(batch_size, self.seq_len, self.num_nodes, self.hidden_dim)
        x_temporal_in = x_temporal_in.permute(0, 2, 1, 3).contiguous().view(batch_size * self.num_nodes, self.seq_len,
                                                                            self.hidden_dim)
        x_temporal_out = self.temporal_module(x_temporal_in)

        x_out_in = x_temporal_out.view(batch_size * self.num_nodes, -1)
        preds = self.output_proj(x_out_in)
        preds = preds.view(batch_size, self.num_nodes, self.pre_len, -1).permute(0, 2, 1, 3).contiguous()

        return preds