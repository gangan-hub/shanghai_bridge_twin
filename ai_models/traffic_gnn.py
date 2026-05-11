import json
import random
import sys
import os
import numpy as np

def run_gnn_inference(start_node=None):
    """
    实际加载 mock_traffic_data.npy 并模拟推演过程。
    如果提供了 start_node，则模拟以该节点为中心的拥堵扩散。
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    traffic_path = os.path.join(current_dir, 'data', 'mock_traffic_data.npy')
    
    try:
        # 加载流量数据 (358, 864)
        traffic_data = np.load(traffic_path)
        num_nodes, total_steps = traffic_data.shape
        
        # 找到 start_node 的索引
        start_idx = -1
        if start_node and start_node.startswith("BRIDGE_"):
            try:
                start_idx = int(start_node.split("_")[1])
            except:
                pass

        # 模拟 12 个时间步的推演 (每个时间步代表 5 分钟)
        steps = []
        for t in range(12):
            # 构建各节点的流量负载
            node_status = {}
            for i in range(num_nodes):
                code = f"BRIDGE_{i:03d}"
                
                if start_idx != -1:
                    # 扩散逻辑：离 start_idx 越近，在越早的时间步变红
                    # 计算索引距离作为拓扑距离的近似
                    dist = abs(i - start_idx)
                    # 随着时间步 t 增加，影响范围扩大 (t * 5 左右的距离)
                    impact_range = t * 8 
                    
                    if dist == 0:
                        # 核心节点始终高拥堵
                        load = 90 + random.randint(0, 10)
                    elif dist < impact_range:
                        # 扩散范围内的节点，负载随距离衰减
                        load = max(40, 90 - dist * 2 + random.randint(-5, 5))
                    else:
                        # 范围外的节点，保持基础负载
                        load = 20 + random.randint(0, 15)
                    node_status[code] = min(100, load)
                else:
                    # 无选中节点，按原始数据展示
                    time_idx = (total_steps - 12 + t) % total_steps
                    val = float(traffic_data[i, time_idx])
                    node_status[code] = min(100, max(0, val / 10.0))
            
            # 模拟连边流量
            edges = []
            if start_idx != -1:
                # 仅展示与扩散相关的连边
                for i in range(max(0, start_idx - 20), min(num_nodes - 1, start_idx + 20)):
                    edges.append({
                        "from": f"BRIDGE_{i:03d}",
                        "to": f"BRIDGE_{i+1:03d}",
                        "flow": node_status[f"BRIDGE_{i:03d}"] * 5 # 流量与负载正相关
                    })
            else:
                for i in range(min(50, num_nodes - 1)):
                    edges.append({
                        "from": f"BRIDGE_{i:03d}",
                        "to": f"BRIDGE_{i+1:03d}",
                        "flow": random.randint(50, 500)
                    })
            
            steps.append({
                "step": t,
                "time_label": f"T+{t*5}min",
                "nodes": node_status,
                "edges": edges
            })
            
        return {
            "status": "success",
            "start_node": start_node,
            "total_steps": 12,
            "data": steps
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    # 从命令行参数获取起始节点
    target = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_gnn_inference(target)
    print(json.dumps(result))
