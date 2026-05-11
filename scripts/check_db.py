import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import psycopg2

conn = psycopg2.connect(host="127.0.0.1", port=5432, dbname="bridge_twin", user="postgres", password="123456")
cur = conn.cursor()

# 检查表是否存在
cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='bridges')")
exists = cur.fetchone()[0]
print(f"bridges 表存在: {exists}")

if exists:
    cur.execute("SELECT COUNT(*) FROM bridges")
    count = cur.fetchone()[0]
    print(f"总行数: {count}")

    if count > 0:
        cur.execute("SELECT node, name, lon, lat, bridge_type, district FROM bridges LIMIT 5")
        for r in cur.fetchall():
            print(f"  node={r[0]}, name={r[1]}, lon={r[2]}, lat={r[3]}, type={r[4]}, district={r[5]}")
    else:
        print("表为空，没有数据！")

conn.close()
