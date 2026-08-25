import torch
import torch.nn as nn
import torch.nn.functional as F

class GCNLayer(nn.Module):
    def __init__(self, in_features, out_features):
        super().__init__()
        self.weight = nn.Parameter(torch.FloatTensor(in_features, out_features))
        self.bias = nn.Parameter(torch.FloatTensor(out_features))
        nn.init.xavier_uniform_(self.weight)
        nn.init.zeros_(self.bias)

    def forward(self, x, adj):
        support = torch.matmul(x, self.weight)
        out = torch.einsum('vw, bwc -> bvc', adj, support)
        return F.relu(out + self.bias)

class GatedDynamicFusion(nn.Module):
    def __init__(self, num_graphs, hidden_dim):
        super().__init__()
        self.linear_o = nn.Linear(num_graphs * hidden_dim, hidden_dim)
        self.linear_w = nn.Linear(num_graphs * hidden_dim, num_graphs)

    def forward(self, graph_features):
        stacked_features = torch.cat(graph_features, dim=-1)
        o = F.relu(self.linear_o(stacked_features))
        w = F.softmax(self.linear_w(stacked_features), dim=-1).unsqueeze(-1)
        separated_features = torch.stack(graph_features, dim=2)
        fused_out = torch.sum(w * separated_features, dim=2)
        return fused_out + o

class MultiGraphSpatialModule(nn.Module):
    def __init__(self, in_dim, hidden_dim):
        super().__init__()
        self.gcn_phys = GCNLayer(in_dim, hidden_dim)
        self.gcn_knn = GCNLayer(in_dim, hidden_dim)
        self.gcn_dtw = GCNLayer(in_dim, hidden_dim)
        self.fusion = GatedDynamicFusion(3, hidden_dim)

    def forward(self, x, adj_phys, adj_knn, adj_dtw):
        out_phys = self.gcn_phys(x, adj_phys)
        out_knn = self.gcn_knn(x, adj_knn)
        out_dtw = self.gcn_dtw(x, adj_dtw)
        return self.fusion([out_phys, out_knn, out_dtw])