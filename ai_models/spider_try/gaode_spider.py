import pandas as pd
import numpy as np
import requests
import time
import os
import sys
from datetime import datetime

# ================= 1. 配置参数 =================
API_KEY = "3113f556d727b3e66680a873eabba494"

# 获取当前脚本所在的目录 (也就是 spider_try 文件夹)
current_dir = os.path.dirname(os.path.abspath(__file__))

# ⚠️ 核心修复：文件就在当前目录下，且精确匹配带有空格的文件名
CSV_PATH = os.path.join(current_dir, '上海市桥梁 POI 数据.csv')

SAVE_CSV_PATH = os.path.join(current_dir, "real_traffic_history.csv")
FINAL_NPY_PATH = os.path.join(current_dir, "real_traffic_data.npy")

# ⚠️ 先测试 1 轮！看看 API 能不能用，跑通后再改成 288
TOTAL_ROUNDS = 1
INTERVAL = 300

# ================= 2. 读取坐标数据 =================
print(f"正在尝试读取数据文件: {CSV_PATH}")
try:
    # 加载当前目录下的 CSV
    poi_df = pd.read_csv(CSV_PATH)
    coords = poi_df[['x', 'y']].values.tolist()
    num_nodes = len(coords)
    print(f"✅ 成功加载 {num_nodes} 座桥梁坐标！")
except Exception as e:
    print(f"❌ 读取 CSV 失败！请检查文件名或文件是否被其他软件(如Excel)占用。\n错误详情: {e}")
    sys.exit()  # 强制打断 PyCharm 控制台


# ================= 3. 高德 API 请求函数 (核心数据说明) =================
def get_traffic_status(lng, lat):
    """
    【爬取数据说明】(写论文时可用)：
    1. 数据来源：高德地图“圆形区域路况 API (v3/traffic/status/circle)”。
    2. 爬取逻辑：输入桥梁的经纬度，检索该桥梁周围 50 米内的【实时拥堵状态】。
    3. 状态码映射：高德原始返回的是 1~4 的状态码，为了让 V-STGRN 深度学习模型能更好地进行数值回归预测，
       我们将离散的状态码映射为连续的虚拟车流量：
       - 1 (畅通) -> 映射为 50 辆/5分钟
       - 2 (缓行) -> 映射为 150 辆/5分钟
       - 3 (拥堵) -> 映射为 300 辆/5分钟
       - 4 (严重拥堵) -> 映射为 500 辆/5分钟
    """
    url = "https://restapi.amap.com/v3/traffic/status/circle"
    params = {
        "key": API_KEY,
        "location": f"{lng},{lat}",
        "radius": 50,
        "extensions": "all",
        "output": "json"
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        res_json = response.json()

        if res_json.get("status") == "1" and "trafficinfo" in res_json:
            eval_data = res_json["trafficinfo"].get("evaluation", {})
            status_code = eval_data.get("status", "0")
            mapping = {"0": 50, "1": 50, "2": 150, "3": 300, "4": 500}
            return mapping.get(str(status_code), 50)
        else:
            if res_json.get("info") != "OK":
                print(f"⚠️ API 返回提示: {res_json.get('info')}")
            return 50
    except Exception as e:
        print(f"请求异常: {e}")
        return 50


# ================= 4. 开始定时爬取 =================
print("\n" + "=" * 50)
print("📊【爬取数据类型说明】📊")
print("目标：爬取上海市桥梁 POI 的实时交通拥堵状态。")
print("转换：将高德拥堵状态码 (1畅通~4严重拥堵) 转换为虚拟车流量 (50~500)。")
print("用途：作为 V-STGRN 模型的真实动态时间序列输入特征 (X 和 Y)。")
print("=" * 50)

print(f"\n🚀 开始执行高德路况爬取任务，当前设定执行 {TOTAL_ROUNDS} 轮...")

traffic_matrix = np.zeros((num_nodes, TOTAL_ROUNDS))

for round_idx in range(TOTAL_ROUNDS):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{current_time}] 开始第 {round_idx + 1}/{TOTAL_ROUNDS} 轮爬取...")

    round_data = []
    for node_idx, (lng, lat) in enumerate(coords):
        flow_value = get_traffic_status(lng, lat)
        traffic_matrix[node_idx, round_idx] = flow_value
        round_data.append(flow_value)

        time.sleep(0.05)  # 防封禁休眠

        if (node_idx + 1) % 50 == 0 or (node_idx + 1) == num_nodes:
            print(f"  -> 已爬取 {node_idx + 1}/{num_nodes} 个节点")

    backup_df = pd.DataFrame([round_data], columns=[f"Node_{i}" for i in range(num_nodes)])
    backup_df.insert(0, "Time", current_time)

    if not os.path.exists(SAVE_CSV_PATH):
        backup_df.to_csv(SAVE_CSV_PATH, index=False, mode='w')
    else:
        backup_df.to_csv(SAVE_CSV_PATH, index=False, mode='a', header=False)

    print(f"✅ 第 {round_idx + 1} 轮爬取完成并已备份。")

    if round_idx < TOTAL_ROUNDS - 1:
        time.sleep(INTERVAL)

# ================= 5. 输出最终模型矩阵 =================
print("\n🎉 测试任务结束！")
np.save(FINAL_NPY_PATH, traffic_matrix)
print(f"💾 已生成真实数据矩阵: {FINAL_NPY_PATH} (形状: {traffic_matrix.shape})")
print("💡 如果上面的打印中没有一直提示 API 错误，说明你的 Key 正常工作！你可以把 TOTAL_ROUNDS 改成 288 去挂机爬取了！")