import pandas as pd
import glob
import os
import re

# 1. 定义文件夹路径和文件匹配模式 (使用 r前缀 防止转义字符报错)
folder_path = r"F:\桌面\Python\V_STGRN_Project\上海备份\data_shanghai\交通数据"
file_pattern = os.path.join(folder_path, "shanghaidata_*.xlsx")

# 2. 获取所有符合条件的文件路径
file_list = glob.glob(file_pattern)


# 3. 对文件列表按序号进行排序，保证按递增顺序检查 (可选)
def extract_number(filepath):
    # 提取文件名中的数字部分，例如 "wuhandata_12.xlsx" 提取出 12
    filename = os.path.basename(filepath)
    match = re.search(r'shanghaidata_(\d+)', filename)
    return int(match.group(1)) if match else 0


file_list.sort(key=extract_number)

print(f"共找到 {len(file_list)} 个文件，开始检查空值...\n")
print("-" * 40)

# 4. 遍历并检查每个文件
files_with_nulls = []

for file_path in file_list:
    file_name = os.path.basename(file_path)
    try:
        # 读取 Excel 文件
        df = pd.read_excel(file_path)

        # df.isnull().values.any() 会检查整个表格，只要有一个单元格为空就返回 True
        if df.isnull().values.any():
            print(f"⚠️ 发现空值: {file_name}")
            files_with_nulls.append(file_name)

    except Exception as e:
        print(f"❌ 读取文件 {file_name} 时发生错误: {e}")

print("-" * 40)
print(f"检查完成！共有 {len(files_with_nulls)} 个文件包含空值。")