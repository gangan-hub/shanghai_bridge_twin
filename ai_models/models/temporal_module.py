import torch
import torch.nn as nn


class MultiScaleRetention(nn.Module):
    def __init__(self, hidden_dim, num_heads):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads

        self.q_proj = nn.Linear(hidden_dim, hidden_dim)
        self.k_proj = nn.Linear(hidden_dim, hidden_dim)
        self.v_proj = nn.Linear(hidden_dim, hidden_dim)
        self.out_proj = nn.Linear(hidden_dim, hidden_dim)

        gammas = 1 - (2 ** (-5 - torch.arange(0, num_heads, dtype=torch.float32)))
        self.register_buffer("gammas", gammas)

    def forward(self, x):
        batch_nodes, seq_len, _ = x.shape
        q = self.q_proj(x).view(batch_nodes, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(batch_nodes, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(batch_nodes, seq_len, self.num_heads, self.head_dim).transpose(1, 2)

        decay_mask = torch.zeros(self.num_heads, seq_len, seq_len, device=x.device)
        for h in range(self.num_heads):
            for i in range(seq_len):
                for j in range(i + 1):
                    decay_mask[h, i, j] = self.gammas[h] ** (i - j)
        decay_mask = decay_mask.unsqueeze(0)

        qk = torch.matmul(q, k.transpose(-1, -2))
        retention = qk * decay_mask
        out = torch.matmul(retention, v)

        out = out.transpose(1, 2).contiguous().view(batch_nodes, seq_len, self.hidden_dim)
        return self.out_proj(out)