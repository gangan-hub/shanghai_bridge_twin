import os
import sys
import numpy as np
import torch
import json
import random
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional

# 将模型路径添加到系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from models.v_stgrn import V_STGRN

app = FastAPI(title="V-STGRN Traffic Prediction API")

# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= 1. 全局配置与模型加载 =================
SEQ_LEN = 12
PRE_LEN = 12
HIDDEN_DIM = 64
NUM_HEADS = 4
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# 全局变量
model = None
traffic_data = None
adj_phys_t = None
adj_knn_t = None
adj_dtw_t = None
mean_val = 0
std_val = 1
num_nodes = 0

def init_model_and_data():
    global model, traffic_data, adj_phys_t, adj_knn_t, adj_dtw_t, mean_val, std_val, num_nodes
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, 'data')
    checkpoint_path = os.path.join(current_dir, 'checkpoints', 'v_stgrn_best.pth')
    
    try:
        # 加载数据
        traffic_data = np.load(os.path.join(data_dir, 'mock_traffic_data.npy'))
        adj_knn = np.load(os.path.join(data_dir, 'knn_adj.npy'))
        adj_dtw = np.load(os.path.join(data_dir, 'dtw_adj.npy'))
        
        num_nodes = traffic_data.shape[0]
        adj_phys = np.eye(num_nodes)
        
        mean_val = np.mean(traffic_data)
        std_val = np.std(traffic_data)
        
        # 转换为 Tensor
        adj_phys_t = torch.FloatTensor(adj_phys).to(DEVICE)
        adj_knn_t = torch.FloatTensor(adj_knn).to(DEVICE)
        adj_dtw_t = torch.FloatTensor(adj_dtw).to(DEVICE)
        
        # 加载模型
        model = V_STGRN(num_nodes=num_nodes, in_dim=1, hidden_dim=HIDDEN_DIM,
                        out_dim=1, seq_len=SEQ_LEN, pre_len=PRE_LEN, num_heads=NUM_HEADS).to(DEVICE)
        
        if os.path.exists(checkpoint_path):
            model.load_state_dict(torch.load(checkpoint_path, map_location=DEVICE))
            model.eval()
            print(f"✅ Model loaded successfully from {checkpoint_path}")
        else:
            print(f"⚠️ Checkpoint not found at {checkpoint_path}, using uninitialized model.")
            
    except Exception as e:
        print(f"❌ Error during initialization: {str(e)}")

# 在启动时初始化
init_model_and_data()

# ================= 2. API 模型定义 =================
class SimulationRequest(BaseModel):
    bridgeCode: str  # 格式如 "BRIDGE_001"

class NodeStatus(BaseModel):
    code: str
    load: float

class EdgeFlow(BaseModel):
    from_node: str
    to_node: str
    flow: float

class SimulationStep(BaseModel):
    step: int
    time_label: str
    nodes: Dict[str, float]
    edges: List[Dict]

class SimulationResponse(BaseModel):
    status: str
    start_node: str
    total_steps: int
    data: List[SimulationStep]

# ================= 3. 核心接口 =================

@app.get("/health")
async def health_check():
    return {"status": "ok", "num_nodes": num_nodes, "device": str(DEVICE)}

@app.post("/api/simulate", response_model=SimulationResponse)
async def simulate(request: SimulationRequest):
    if model is None:
        raise HTTPException(status_code=500, detail="Model not initialized")
        
    start_node = request.bridgeCode
    try:
        start_idx = int(start_node.split("_")[1])
    except:
        raise HTTPException(status_code=400, detail="Invalid bridgeCode format. Expected BRIDGE_XXX")
    
    if start_idx < 0 or start_idx >= num_nodes:
        raise HTTPException(status_code=400, detail=f"Node index out of range (0-{num_nodes-1})")

    # 1. 准备输入数据 (制造攻击剧本)
    # 取最近的 SEQ_LEN 个时间步
    X_raw = traffic_data[:, -SEQ_LEN:].copy()
    
    # 模拟攻击：将目标节点流量拉满
    # 调整攻击值，使其产生约 150-200 的流量，触发红区
    X_raw[start_idx, -3:] = 600 + random.randint(0, 100) 
    
    # 对所有节点增加基础水位，使其自然分布在 40-100 之间，容易触发橙/红区
    X_raw = X_raw + 150
    noise = np.random.normal(0, 50, X_raw.shape)
    X_raw = np.maximum(0, X_raw + noise)
    
    # 归一化
    X_norm = (X_raw - mean_val) / std_val
    X_tensor = torch.FloatTensor(X_norm.T).unsqueeze(0).unsqueeze(-1).to(DEVICE)
    
    # 2. 运行 V-STGRN 模型推演
    with torch.no_grad():
        preds = model(X_tensor, adj_phys_t, adj_knn_t, adj_dtw_t)
        
    # 3. 反归一化处理结果
    preds_np = preds.squeeze().cpu().numpy() # (PRE_LEN, num_nodes)
    preds_real = (preds_np * std_val) + mean_val
    preds_real = np.maximum(0, preds_real)
    
    # 4. 构造前端需要的格式
    steps = []
    for t in range(PRE_LEN):
        node_status = {}
        for i in range(num_nodes):
            code = f"BRIDGE_{i:03d}"
            # 将真实流量映射为 0-100 的负载比例 (假设 1000 为满载)
            load = min(100, max(0, (preds_real[t, i] / 10.0)))
            node_status[code] = float(load)
            
        # 模拟扩散相关的边 (为了演示效果，显示 start_idx 周边的流量)
        edges = []
        # 简单模拟拓扑连线
        for i in range(max(0, start_idx - 20), min(num_nodes - 1, start_idx + 20)):
            edges.append({
                "from": f"BRIDGE_{i:03d}",
                "to": f"BRIDGE_{i+1:03d}",
                "flow": float(node_status[f"BRIDGE_{i:03d}"] * 8)
            })
            
        steps.append(SimulationStep(
            step=t,
            time_label=f"T+{t*5}min",
            nodes=node_status,
            edges=edges
        ))
        
    return SimulationResponse(
        status="success",
        start_node=start_node,
        total_steps=PRE_LEN,
        data=steps
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
