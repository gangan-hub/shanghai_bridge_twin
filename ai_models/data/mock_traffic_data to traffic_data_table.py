import numpy as np
import pandas as pd

# 1. 读取 .npy 数据 (请确保路径正确，如果在同一目录下直接写文件名即可)
data = np.load('mock_traffic_data.npy')

print(f"原始数据形状: {data.shape}")

# 2. 生成行名和列名，让表格更容易看懂
# 行名：Node_0, Node_1 ... Node_357
node_names = [f"Node_{i}" for i in range(data.shape[0])]
# 列名：Time_1, Time_2 ... Time_864
time_steps = [f"Time_{i+1}" for i in range(data.shape[1])]

# 3. 转换为 Pandas DataFrame (二维数据表)
df = pd.DataFrame(data, index=node_names, columns=time_steps)

# 4. 导出为 CSV 文件
output_filename = 'traffic_data_table.csv'
df.to_csv(output_filename)

print(f"✅ 大功告成！数据已成功导出为表格文件：{output_filename}")