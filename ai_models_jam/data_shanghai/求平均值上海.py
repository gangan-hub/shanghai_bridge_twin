import os
import pandas as pd
import glob

# ==========================================
# 1. 直接使用你提供的绝对路径 (Windows 格式)
# ==========================================
# 数据主目录
DATA_DIR = r"F:\Trae code\002\ai_models_jam\data_shanghai"
# 交通时间切片数据目录
TRAFFIC_DIR = os.path.join(DATA_DIR, "data_traffic")

# 原始的桥梁基础表 (请确保这个文件存在于 data_shenzhen 文件夹下)
BASE_BRIDGE_FILE = os.path.join(DATA_DIR, "上海市桥梁列表.xlsx")
# 聚合后输出的新文件 (将作为第一段代码的新输入)
OUTPUT_FILE = os.path.join(DATA_DIR, "Shanghai_Bridge_List_Averages.xlsx")

def calculate_baseline_features():
    print(f"开始扫描文件夹: {TRAFFIC_DIR}")

    # 匹配所有的 shenzhendata_*.xlsx 文件
    file_pattern = os.path.join(TRAFFIC_DIR, "shanghaidata_*.xlsx")
    all_files = glob.glob(file_pattern)

    if not all_files:
        print("❌ 未找到任何动态交通数据文件，请检查文件夹里是否有 shanghaidata_0.xlsx 等文件！")
        return

    print(f"✅ 共找到 {len(all_files)} 个时间切片文件，正在疯狂读取中...")

    # 2. 遍历所有文件并合并
    df_list = []
    for file in all_files:
        try:
            # 只读取 node, flow, congestion，大幅节省内存和时间
            df = pd.read_excel(file, usecols=['node', 'flow', 'congestion'])
            df_list.append(df)
        except Exception as e:
            print(f"读取文件 {file} 失败，跳过。原因: {e}")

    # 将所有切片纵向拼接成一个超大表
    master_df = pd.concat(df_list, ignore_index=True)

    print("⏳ 正在计算每座桥梁的历史平均值 (基准特征)...")

    # 3. 按 node(桥梁) 分组求均值
    avg_df = master_df.groupby('node', as_index=False)[['flow', 'congestion']].mean()

    # 保留两位小数，数据更清爽
    avg_df['flow'] = avg_df['flow'].round(2)
    avg_df['congestion'] = avg_df['congestion'].round(2)

    print("⏳ 正在与原桥梁拓扑表合并...")

    # 4. 读取原始的基础拓扑表
    if not os.path.exists(BASE_BRIDGE_FILE):
        print(f"❌ 找不到基础拓扑文件: {BASE_BRIDGE_FILE}")
        return

    base_bridge_df = pd.read_excel(BASE_BRIDGE_FILE)

    # 清理旧数据：如果原表里已经有了 flow 和 congestion 列，先删掉它们
    if 'flow' in base_bridge_df.columns:
        base_bridge_df = base_bridge_df.drop(columns=['flow'])
    if 'congestion' in base_bridge_df.columns:
        base_bridge_df = base_bridge_df.drop(columns=['congestion'])

    # 5. 合并均值数据 (左连接保证所有桥梁都在)
    final_df = pd.merge(base_bridge_df, avg_df, on='node', how='left')

    # 填补空缺：如果某座桥从未在动态数据里出现过，给个默认值
    final_df['flow'] = final_df['flow'].fillna(0)
    final_df['congestion'] = final_df['congestion'].fillna(1.0)

    # 6. 保存最终文件
    final_df.to_excel(OUTPUT_FILE, index=False)
    print(f"\n🎉 处理大功告成！\n均值基准表已保存至:\n👉 {OUTPUT_FILE}")
    print("\n【下一步该干嘛？】")
    print("回到你发给我的第一段代码 (Node2Vec)，把里面读取的:")
    print("node_excel_paths = [os.path.join(BASE_DIR, '../data_shanghai/上海市桥梁列表.xlsx')]")
    print("改成新生成的文件:")
    print("node_excel_paths = [os.path.join(BASE_DIR, '../data_shanghai/上海市桥梁列表_均值基准.xlsx')]")
    print("然后重新跑一次第一段代码生成新的 Embedding，你的整个系统逻辑就完美闭环了！")


if __name__ == "__main__":
    calculate_baseline_features()