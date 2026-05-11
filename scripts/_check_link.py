import sys, json
sys.path.insert(0, r"f:\Trae code\002\.pydeps")
import psycopg2
import pandas as pd

# 1. 数据库 node_0base
c = psycopg2.connect(host="127.0.0.1", port=5432, database="bridge_twin", user="postgres", password="123456")
cur = c.cursor()
cur.execute("SELECT node_0base, name, wgs_lon, wgs_lat FROM bridges ORDER BY node_0base")
rows = cur.fetchall()
c.close()
print("DB 记录数:", len(rows))
print("DB node_0base 范围:", rows[0][0], "~", rows[-1][0])
print("DB node_0base 前10:", [r[0] for r in rows[:10]])
print("DB 有坐标数:", sum(1 for r in rows if r[2] is not None and r[3] is not None))

# 2. CSV 索引
csv_path = r"f:\Trae code\002\ai_models_flow\shanghai_data\generate_acc_shanghai\link_matrix_shanghai.csv"
adj = pd.read_csv(csv_path, index_col=0)
adj.index = adj.index.astype(str)
n = len(adj.index)
print("\nCSV 节点数:", n)
print("CSV 索引前10:", adj.index[:10].tolist())

# 3. 计算连线数（weight>0，上三角）
links = 0
for i in range(n):
    for j in range(i + 1, n):
        raw = adj.iloc[i, j]
        if pd.isna(raw):
            continue
        if float(raw) > 0:
            links += 1
print("CSV weight>0 连线数:", links)

# 4. 匹配验证：node_0base 是否 0-based 且与 CSV 行号一致
node_set = set(r[0] for r in rows)
match_0based = sum(1 for i in range(n) if i in node_set)
match_1based = sum(1 for i in range(n) if (i + 1) in node_set)
print("\n与 CSV 0-based 索引匹配数:", match_0based)
print("与 CSV 1-based 索引匹配数:", match_1based)
