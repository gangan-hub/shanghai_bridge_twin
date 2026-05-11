import os
import math
import pandas as pd
import folium
import json


# 核心修复：节点 ID 清洗函数，确保 Excel 的 ID 和矩阵行列名 100% 匹配
def clean_id(x):
    try:
        return str(int(float(x)))
    except:
        return str(x).strip()


# ================= 1. 本地文件路径配置 =================
current_dir = os.getcwd()

# 1. 节点数据表 (包含中点坐标)
input_excel = r"f:\Trae code\002\ai_models_flow\shanghai_data\shanghaidata_x.xlsx"

# 2. 真实路网邻接矩阵 CSV 文件
link_matrix_csv = r"f:\Trae code\002\ai_models_flow\shanghai_data\generate_acc_shanghai\link_matrix_shanghai.csv"

# 3. 🚦 流量预测与折线图 JSON 数据路径
prediction_json_path = r"F:\桌面\Python\V_STGRN_Project\traffic_prediction\results\frontend_map_data.json"
chart_json_path = r"F:\桌面\Python\V_STGRN_Project\traffic_prediction\results\frontend_chart_data.json"

# 4. 输出路径
output_dir = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
output_html = os.path.join(output_dir, "中点网络连线_全量底图版_上海.html")

print(">>> 1. 正在读取节点数据、邻接矩阵及JSON数据...")
try:
    df = pd.read_excel(input_excel)
    adj_matrix = pd.read_csv(link_matrix_csv, index_col=0)
    adj_matrix.index = adj_matrix.index.astype(str)
    adj_matrix.columns = adj_matrix.columns.astype(str)
except Exception as e:
    raise FileNotFoundError(f"❌ 读取 Excel 或 CSV 失败，请检查路径。\n报错: {e}")

# ---------- 🔧 关键修复 1：列名显式绑定（硬编码 columns[3]/[4] 改为具名列，防止列顺序乱掉）----------
# 百度 BD09 坐标系经纬度（x=经度/Lon, y=纬度/Lat）→ 转 WGS84
if 'x' in df.columns and 'y' in df.columns:
    COL_BD09_LNG = 'x'   # 百度经度（度）
    COL_BD09_LAT = 'y'   # 百度纬度（度）
else:
    # 兼容老版本：fallback 到第 3/4 列
    COL_BD09_LNG = df.columns[3]
    COL_BD09_LAT = df.columns[4]

# ---------- 🔧 关键修复 2：分工 / 桥隧类型 / 车道数 / 路名 / 行政区 等功能元数据列 ----------
META_COLS = {
    'func_name':   '分工',         # ✅ 用户说的「功能名称」
    'bridge_type': '桥隧类型',     # 梁桥/拱桥/悬索桥 等
    'road_class':  'road_class',   # 快速路/主干道/次干道
    'lanes':       '车道数',       # 2/4/6/8
    'district':    'adname',       # 杨浦区 / 浦东新区
    'road_name':   'roadname',     # 所属路名
    'poi_flow':    'poi',          # 基准流量参考值
    'typecode':    'typecode',     # POI 分类码
}
for k, v in META_COLS.items():
    if v not in df.columns:
        print(f"  ⚠️ xlsx 缺少列 '{v}'（映射 {k}），将使用默认空值")


# 读取流量推演JSON（紧跟 xlsx 读取之后）
forecast_data_json_str = "{}"
try:
    if os.path.exists(prediction_json_path):
        with open(prediction_json_path, 'r', encoding='utf-8') as f:
            forecast_data_json_str = json.dumps(json.load(f))
except Exception as e:
    print(f"⚠️ 无法读取推演 JSON ({prediction_json_path})")

# 读取图表数据JSON (确保严格转为 JSON 字符串供前端调用)
chart_data_json_str = "[]"
try:
    if os.path.exists(chart_json_path):
        with open(chart_json_path, 'r', encoding='utf-8') as f:
            chart_data_json_str = json.dumps(json.load(f))
except Exception as e:
    print(f"⚠️ 无法读取折线图 JSON ({chart_json_path})")


# ================= 2. 底层坐标转换算法 (BD09 -> GCJ02 -> WGS84) =================
x_pi = 3.14159265358979324 * 3000.0 / 180.0
pi = 3.1415926535897932384626
a = 6378245.0
ee = 0.00669342162296594323


def transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * pi) + 20.0 * math.sin(2.0 * x * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * pi) + 40.0 * math.sin(y / 3.0 * pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * pi) + 320 * math.sin(y * pi / 30.0)) * 2.0 / 3.0
    return ret


def transform_lon(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * pi) + 20.0 * math.sin(2.0 * x * pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * pi) + 40.0 * math.sin(x / 3.0 * pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * pi) + 300.0 * math.sin(x / 30.0 * pi)) * 2.0 / 3.0
    return ret


def bd09_to_gcj02(bd_lon, bd_lat):
    x = bd_lon - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * x_pi)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * x_pi)
    gg_lng = z * math.cos(theta)
    gg_lat = z * math.sin(theta)
    return gg_lng, gg_lat


def gcj02_to_wgs84(lng, lat):
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lon(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * pi)
    mglat = lat + dlat
    mglng = lng + dlng
    return lng * 2 - mglng, lat * 2 - mglat


def get_coord(row, col_lng, col_lat):
    try:
        if pd.isna(row[col_lng]) or pd.isna(row[col_lat]):
            return None, None
        return float(row[col_lng]), float(row[col_lat])
    except:
        return None, None


# ================= 3. 中点坐标转换与哈希表构建 =================
print(">>> 2. 正在进行中点坐标转换并将节点注册到哈希表...")

nodes_dict = {}
valid_wgs_lats, valid_wgs_lons = [], []

def _val(row, col, default=None):
    """安全读取单元格（缺列/NaN 时 fallback）"""
    if col not in row.index:
        return default
    v = row[col]
    if pd.isna(v):
        return default
    if isinstance(v, str):
        s = v.strip()
        return s if s else default
    return v

for index, row in df.iterrows():
    # 1) 节点原始 0 基序号（严格对齐 link_matrix_shanghai.csv 的行/列 index）
    if 'node' in df.columns:
        node_raw = _val(row, 'node', index)
        node_id = clean_id(node_raw)
    elif 'Unnamed: 0' in df.columns:
        node_raw = _val(row, 'Unnamed: 0', index)
        node_id = clean_id(node_raw)
    else:
        node_raw = index
        node_id = f"Node_{index}"

    # 2) ✅ 严格执行「node + 1 = display_idx」用户要求
    try:
        display_id = str(int(float(node_raw)) + 1)
    except Exception:
        # 如果不是数字（fallback），仍保留原值：不破坏匹配
        display_id = str(node_id)

    # 3) 基础名称
    node_name = str(_val(row, 'name', f'节点_{display_id}'))

    # 4) ✅ 功能名称 + 元数据（分工/桥隧类型/车道数/路名/行政区/参考流量）
    func_name   = str(_val(row, META_COLS['func_name'],   '-'))
    bridge_type = str(_val(row, META_COLS['bridge_type'], '-'))
    road_class  = str(_val(row, META_COLS['road_class'],  '-'))
    lanes       = _val(row, META_COLS['lanes'], None)
    district    = str(_val(row, META_COLS['district'],    '-'))
    road_name   = str(_val(row, META_COLS['road_name'],   '-'))
    poi_flow    = _val(row, META_COLS['poi_flow'], None)
    typecode    = _val(row, META_COLS['typecode'], None)

    lanes_str = str(int(lanes)) if lanes is not None else '-'

    # 5) BD09(百度) → GCJ02(火星) → WGS84(国际) 转换
    #    COL_BD09_LNG = 'x'（百度经度，度）；COL_BD09_LAT = 'y'（百度纬度，度）
    bd_lon, bd_lat = get_coord(row, COL_BD09_LNG, COL_BD09_LAT)

    if bd_lon is not None:
        gcj_lon, gcj_lat = bd09_to_gcj02(bd_lon, bd_lat)
        wgs_lon, wgs_lat = gcj02_to_wgs84(gcj_lon, gcj_lat)

        nodes_dict[node_id] = {
            # ===== 核心索引 =====
            'node_0base':  int(float(node_raw)),       # 原始 0 基（对齐 link_matrix CSV）
            'display_id':  display_id,                  # ✅ node+1，页面显示用
            'name':        node_name,

            # ===== ✅ 功能元数据（用户要求） =====
            'func_name':   func_name,                   # 分工（功能名称）
            'bridge_type': bridge_type,                 # 桥隧类型
            'road_class':  road_class,                  # 快速路/主干道/次干道
            'lanes':       lanes_str,                   # 车道数
            'district':    district,                    # 行政区
            'road_name':   road_name,                   # 所属路名
            'poi_flow':    poi_flow,                    # POI 参考流量
            'typecode':    typecode,                    # POI 编码

            # ===== 坐标（纬度在前，Folium location=[lat, lon] 惯例） =====
            'BD09':  [bd_lat,  bd_lon],
            'GCJ02': [gcj_lat, gcj_lon],
            'WGS84': [wgs_lat, wgs_lon],
        }
        valid_wgs_lats.append(wgs_lat)
        valid_wgs_lons.append(wgs_lon)

print(f"  - 成功载入 {len(nodes_dict)} 个节点（0基 node 0~{len(nodes_dict)-1}；显示序号 1~{len(nodes_dict)}）")

# ================= 4. 渲染地图底图 =================
print(">>> 3. 正在生成全图层映射地图...")

if valid_wgs_lats:
    center_map = [sum(valid_wgs_lats) / len(valid_wgs_lats), sum(valid_wgs_lons) / len(valid_wgs_lons)]
else:
    center_map = [22.543099, 114.057868]

m = folium.Map(location=center_map, zoom_start=12, tiles=None)

# ----------------- 挂载最全 25 款底图 -----------------
folium.TileLayer(tiles='https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png', attr='CartoDB',
                 name='🟢 [暗黑科技] CartoDB Dark (WGS84)', show=False).add_to(m)
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attr='ESRI', name='🟢 [暗黑灰阶] ESRI Dark (WGS84)', show=False).add_to(m)
folium.TileLayer(tiles='https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png', attr='CartoDB',
                 name='🟢 [浅色极简] CartoDB Positron (WGS84)', show=False).add_to(m)
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attr='ESRI', name='🟢 [浅色灰阶] ESRI Light Gray (WGS84)', show=False).add_to(m)
folium.TileLayer(tiles='https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png', attr='CartoDB',
                 name='🟢 [彩色清爽] CartoDB Voyager (WGS84)', show=False).add_to(m)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google',
                 name='🟢 [卫星影像] Google 国际高清卫星 (WGS84)', show=False).add_to(m)
folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google',
                 name='🟢 [卫星混合] Google 卫星混合 (WGS84)', show=False).add_to(m)
folium.TileLayer(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                 attr='ESRI', name='🟢 [卫星影像] ESRI 国际高清卫星 (WGS84)', show=False).add_to(m)
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}',
    attr='ESRI', name='🟢 [国家地理] ESRI 经典地形图 (WGS84)', show=False).add_to(m)
folium.TileLayer(tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', attr='OpenTopoMap',
                 name='🟢 [三维地形] OpenTopoMap 等高线 (WGS84)', show=False).add_to(m)
folium.TileLayer(tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', attr='OSM',
                 name='🟢 [平面路网] OSM 国际经典街道 (WGS84)', show=False).add_to(m)
folium.TileLayer(
    tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    attr='ESRI', name='🟢 [平面路网] ESRI 国际街道 (WGS84)', show=False).add_to(m)

folium.TileLayer(
    tiles='http://map.geoq.cn/ArcGIS/rest/services/ChinaOnlineStreetPurplishBlue/MapServer/tile/{z}/{y}/{x}',
    attr='GeoQ', name='💠 [科技蓝] 智图 GeoQ 大屏版 (推荐/GCJ02)', show=True).add_to(m)
folium.TileLayer(tiles='http://map.geoq.cn/ArcGIS/rest/services/ChinaOnlineStreetGray/MapServer/tile/{z}/{y}/{x}',
                 attr='GeoQ', name='💠 [高级灰] 智图 GeoQ 水墨灰 (GCJ02)', show=False).add_to(m)
folium.TileLayer(tiles='http://map.geoq.cn/ArcGIS/rest/services/ChinaOnlineStreetWarm/MapServer/tile/{z}/{y}/{x}',
                 attr='GeoQ', name='💠 [暖色调] 智图 GeoQ 暖色系 (GCJ02)', show=False).add_to(m)
folium.TileLayer(tiles='http://map.geoq.cn/ArcGIS/rest/services/ChinaOnlineCommunity/MapServer/tile/{z}/{y}/{x}',
                 attr='GeoQ', name='💠 [标准彩] 智图 GeoQ 多彩路网 (GCJ02)', show=False).add_to(m)
folium.TileLayer(tiles='https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}',
                 attr='Amap', name='🟠 [平面路网] 高德常规街道 (GCJ02)', show=False).add_to(m)
folium.TileLayer(tiles='https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
                 attr='Amap', name='🟠 [平面路网] 高德精简街道 (GCJ02)', show=False).add_to(m)
folium.TileLayer(tiles='https://webst02.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}', attr='Amap',
                 name='🟠 [卫星影像] 高德纯实景卫星 (无路名)', show=False).add_to(m)
folium.TileLayer(tiles='https://webst02.is.autonavi.com/appmaptile?style=8&x={x}&y={y}&z={z}', attr='Amap',
                 name='🟠 [路网注记] 高德透明地名与边界 (无底色)', show=False).add_to(m)

folium.TileLayer(tiles='http://api2.map.bdimg.com/customimage/tile?&x={x}&y={y}&z={z}&customid=dark', attr='Baidu',
                 name='🟣 [科技蓝] 百度定制版蓝黑 (BD09)', show=False).add_to(m)
folium.TileLayer(tiles='http://api2.map.bdimg.com/customimage/tile?&x={x}&y={y}&z={z}&customid=midnight', attr='Baidu',
                 name='🟣 [午夜深色] 百度个性化暗黑 (BD09)', show=False).add_to(m)
folium.TileLayer(tiles='http://api2.map.bdimg.com/customimage/tile?&x={x}&y={y}&z={z}&customid=light', attr='Baidu',
                 name='🟣 [清新浅色] 百度个性化浅色 (BD09)', show=False).add_to(m)
folium.TileLayer(tiles='http://online1.map.bdimg.com/onlinelabel/?qt=tile&x={x}&y={y}&z={z}&styles=pl', attr='Baidu',
                 name='🟣 [平面路网] 百度经典街道 (BD09)', show=False).add_to(m)
folium.TileLayer(tiles='http://shanghai.map.bdimg.com/it/u=x={x};y={y};z={z};v=009;type=sgeo&fm=46', attr='Baidu',
                 name='🟣 [卫星影像] 百度高清卫星 (BD09)', show=False).add_to(m)

fg_wgs84 = folium.FeatureGroup(name="✔️ 启用 国际标准 WGS-84 数据层", show=False)
fg_gcj02 = folium.FeatureGroup(name="✔️ 启用 中国火星 GCJ-02 数据层", show=True)
fg_bd09 = folium.FeatureGroup(name="✔️ 启用 百度私有 BD-09 数据层", show=False)

COLOR_NODE = '#00FFAA'  # 圆点颜色：薄荷绿
COLOR_EDGE = '#0066FF'    # 连线颜色：科技蓝

# ================= 5. 精准绘制网络拓扑 =================
print(">>> 4. 正在根据矩阵权重精准编织网络关系...")

for node_id, data in nodes_dict.items():
    for sys_name, fg in [('WGS84', fg_wgs84), ('GCJ02', fg_gcj02), ('BD09', fg_bd09)]:
        pt = data[sys_name]
        d_id = data['display_id']
        name = data['name']
        func      = data['func_name']
        btype     = data['bridge_type']
        rclass    = data['road_class']
        lanes     = data['lanes']
        district  = data['district']
        roadname  = data['road_name']
        poiflow   = ('%.0f' % float(data['poi_flow'])) if data['poi_flow'] is not None else '-'

        # -------- tooltip：完整功能名称信息（用户要求准确显示功能名称）--------
        tooltip_html = f"""
        <div style="font-family:'PingFang SC','Microsoft YaHei',sans-serif; min-width: 230px;">
          <b style="color:#00FFAA; font-size: 14px;">[{d_id}] {name}</b><br>
          <span style="color:#94A3B8; font-size:12px;">原始 0 基 node：{data['node_0base']}</span><hr style="margin:6px 0; border-color:#334155;">
          🔧 <b>功能（分工）：</b><span style="color:#38BDF8;">{func}</span><br>
          🏗️ <b>桥隧类型：</b>{btype} &nbsp;·&nbsp; <b>车道数：</b>{lanes}<br>
          🛣️ <b>道路等级：</b>{rclass} &nbsp;·&nbsp; <b>所属路：</b>{roadname}<br>
          📍 <b>行政区：</b>{district} &nbsp;·&nbsp; <b>POI 参考流量：</b><span style="color:#FACC15;">{poiflow}</span><br>
          <span style="color:#64748B; font-size:11px;">坐标系：{sys_name}</span>
        </div>"""

        # 底层静态白边圆圈（颜色方案完全保留原配置 COLOR_NODE）
        folium.CircleMarker(
            location=pt, radius=4.0, color='#FFFFFF', weight=1.0,
            fill=True, fill_color=COLOR_NODE, fill_opacity=1.0, z_index=999,
            tooltip=folium.Tooltip(tooltip_html, style="background:#1E293B; color:#E2E8F0; border:1px solid #00FFAA; border-radius:8px; padding:8px 10px;")
        ).add_to(fg)

        # -------- 玻璃态标签（功能名显示：display_id | 名称 | 功能分工）--------
        label_full_parts = []
        label_full_parts.append(f"""<span class="bridge-node" style="font-family:'SF Pro Display',sans-serif;font-weight:900;font-size:13px;color:#059669;padding-right:4px;text-shadow:0 0 3px rgba(255,255,255,0.9);">{d_id}</span>""")
        label_full_parts.append(f"""<span class="bridge-separator" style="color:rgba(15,23,42,0.30);font-size:12px;font-weight:300;">|</span>""")
        label_full_parts.append(f"""<span class="bridge-name" style="font-family:'PingFang SC',sans-serif;font-weight:600;font-size:12px;color:#0F172A;padding:0 4px;letter-spacing:0.5px;text-shadow:0 0 4px rgba(255,255,255,0.9);">{name}</span>""")
        if func and func != '-':
            label_full_parts.append(f"""<span class="bridge-separator bridge-sep-func" style="color:rgba(15,23,42,0.30);font-size:12px;font-weight:300;">|</span>""")
            label_full_parts.append(f"""<span class="bridge-func" style="font-family:'PingFang SC',sans-serif;font-weight:500;font-size:11px;color:#0369A1;padding-left:4px;letter-spacing:0.4px;text-shadow:0 0 3px rgba(255,255,255,0.9);">{func}</span>""")
        label_html_inner = "".join(label_full_parts)

        # -------- 🌟 DOM 结构：增加功能名称，同时 openChart 把功能名/类型也传进去 --------
        html_content = f'''
            <div id="ui-node-{node_id}" style="position: relative; cursor: pointer; width: 0; height: 0;"
                 onclick=\'openChart("{node_id}", "{name}", "{d_id}", "{func}", "{btype}", "{lanes}", "{roadname}", "{district}")\'>

                <div class="dynamic-node" style="display:none; position: absolute; left: 0; top: 0; transform: translate(-50%, -50%);
                        width: 14px; height: 14px; border-radius: 50%; border: 2px solid #FFF;
                        box-shadow: 0 0 12px #00FFAA; background-color: #00FFAA; transition: 0.3s all;">
                </div>

                <div class="glass-label-wrapper" style="position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%); display: none; align-items: stretch;
                            background: rgba(255, 255, 255, 0.25); backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
                            border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.4); box-shadow: 0 4px 10px rgba(0,0,0,0.08);
                            pointer-events: auto; transition: all 0.2s ease; overflow: hidden;">

                    <div class="label-text-container" style="padding: 4px 10px; display: flex; align-items: center; white-space: nowrap;">
                        {label_html_inner}
                    </div>

                    <div class="flow-badge-container" style="display: none; align-items: center; background: rgba(255, 255, 255, 0.15); border-left: 2px solid #10B981; padding: 0 10px;">
                        <span class="flow-badge-icon" style="font-size: 11px; margin-right: 4px;">🚗</span>
                        <span class="flow-badge-text" style="font-family:'SF Pro Display',sans-serif;font-size:14px;font-weight:900;color:#10B981;text-shadow:0 1px 3px rgba(255,255,255,0.9);padding-bottom:1px;">--</span>
                    </div>
                </div>
            </div>'''

        folium.Marker(
            location=pt,
            icon=folium.DivIcon(icon_size=(0, 0), icon_anchor=(0, 0), html=html_content)
        ).add_to(fg)

# 2. 连线
nodes_in_matrix = adj_matrix.index.tolist()
num_nodes = len(nodes_in_matrix)
connected_edges = 0
for i in range(num_nodes):
    for j in range(i + 1, num_nodes):
        node_a_id = nodes_in_matrix[i]
        node_b_id = nodes_in_matrix[j]
        weight = adj_matrix.iloc[i, j]

        if pd.notna(weight) and float(weight) > 0:
            if node_a_id in nodes_dict and node_b_id in nodes_dict:
                connected_edges += 1
                node_a_data = nodes_dict[node_a_id]
                node_b_data = nodes_dict[node_b_id]
                for sys_name, fg in [('WGS84', fg_wgs84), ('GCJ02', fg_gcj02), ('BD09', fg_bd09)]:
                    folium.PolyLine(
                        [node_a_data[sys_name], node_b_data[sys_name]], color=COLOR_EDGE, weight=1.5, opacity=0.6,
                        tooltip=f"<b>网络连线</b><br>{node_a_data['name']} <-> {node_b_data['name']}<br>权重: {float(weight):.4f}"
                    ).add_to(fg)

print(f"  - 成功匹配并绘制了 {connected_edges} 条拓扑连线！")

fg_wgs84.add_to(m)
fg_gcj02.add_to(m)
fg_bd09.add_to(m)
folium.LayerControl(position='topright', collapsed=False).add_to(m)

# ================= 6. 科技感 HTML 注入 =================
# 预计算所有节点的三坐标系数据，供前端连线更新使用
node_coords_all = {}
for node_id, data in nodes_dict.items():
    idx = data['node_0base']
    node_coords_all[idx] = {
        'bd09': data['BD09'],
        'gcj02': data['GCJ02'],
        'wgs84': data['WGS84']
    }

bridge_info = {
    data['node_0base']: {
        'name': data['name'],
        'func': data['func_name'],
        'lat': data['BD09'][0],
        'lng': data['BD09'][1],
        'wgs84_lat': data['WGS84'][0],
        'wgs84_lng': data['WGS84'][1],
        'gcj02_lat': data['GCJ02'][0],
        'gcj02_lng': data['GCJ02'][1]
    } for node_id, data in nodes_dict.items()
}
bridge_info_json = json.dumps(bridge_info, ensure_ascii=False)
node_coords_json = json.dumps(node_coords_all, ensure_ascii=False)

# 🚨 注入 ECharts CDN、控制台及JS解析引擎
html_injection = f'''
<!-- 引入 ECharts -->
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>

<style id="dynamic-label-styles">
    input[type=range] {{ -webkit-appearance: none; width: 100%; background: transparent; }}
    input[type=range]::-webkit-slider-runnable-track {{ width: 100%; height: 6px; cursor: pointer; background: #4B5563; border-radius: 3px; }}
    input[type=range]::-webkit-slider-thumb {{ height: 16px; width: 16px; border-radius: 50%; background: #FFFFFF; border: 2px solid #3B82F6; cursor: pointer; -webkit-appearance: none; margin-top: -5px; }}
    .glass-select {{ flex: 1; background: rgba(15, 23, 42, 0.6); color: #E2E8F0; border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 4px; padding: 6px; font-family: 'PingFang SC', sans-serif; font-size: 13px; outline: none; cursor: pointer; transition: 0.3s; }}
    .glass-select:focus {{ border-color: #00FFAA; box-shadow: 0 0 5px rgba(0, 255, 170, 0.5); }}
</style>

<!-- 控制台面板 -->
<div style="position: fixed; top: 20px; left: 20px; width: 340px; z-index:9000; color: white; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;">

    <h2 style="margin: 0 0 15px 0; font-size:20px; font-weight:bold; background: linear-gradient(90deg, #00FFAA, #38BDF8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: 1px; text-align: center; display: block;">空间网络拓扑底座</h2>

    <!-- 交通流实时预测系统模块 -->
    <div style="margin-bottom: 15px; background: rgba(30, 41, 59, 0.85); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); backdrop-filter: blur(8px);">
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <span style="font-size: 16px; margin-right: 6px;">⚡</span>
            <span style="font-size: 15px; font-weight: bold; color: #10B981;">交通流实时预测系统</span>
        </div>

        <div style="display: flex; gap: 10px; margin-bottom: 12px;">
            <select id="day-select" class="glass-select">
                <option value="1">星期一</option><option value="2">星期二</option><option value="3">星期三</option>
                <option value="4">星期四</option><option value="5">星期五</option><option value="6">星期六</option><option value="7">星期日</option>
            </select>
            <select id="time-select" class="glass-select">
                <script>
                    for(let i=0; i<24; i++) {{
                        let hour = i.toString().padStart(2, '0');
                        document.write(`<option value="${{hour}}">${{hour}}:00</option>`);
                    }}
                </script>
            </select>
        </div>

        <button id="play-btn" onclick="togglePrediction()" style="width: 100%; padding: 10px; background: #10B981; color: white; border: none; border-radius: 4px; font-size: 14px; font-weight: bold; cursor: pointer; transition: 0.3s; box-shadow: 0 2px 6px rgba(0,0,0,0.2);">
            ▶ 启动 AI 预测引擎
        </button>

        <div id="pred-timeline-container" style="margin-top: 15px; text-align: center; display: none;">
            <div id="pred-time-label" style="font-size: 14px; color: #FFFFFF; font-weight: bold; margin-bottom: 8px;">预测推演时间: 正在加载...</div>
            <input type="range" id="pred-slider" min="0" max="0" value="0" step="1" oninput="onSliderChange()">
        </div>
    </div>

    <!-- 图层显示控制模块 -->
    <div style="margin-bottom: 15px; background: rgba(30, 41, 59, 0.85); border-radius: 8px; padding: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); backdrop-filter: blur(8px);">
        <div style="color: #94A3B8; font-size: 13px; margin-bottom: 10px;">【图层显示控制】</div>
        <!-- 初始状态取消 checkbox 勾选 -->
        <div style="display: flex; flex-wrap: wrap; gap: 12px 20px; font-size: 14px; color: #FFFFFF;">
            <label style="display: flex; align-items: center; cursor: pointer;">
                <input type="checkbox" id="toggle-nodes" checked onchange="updateLabelStyles()" style="margin-right: 6px; accent-color: #3B82F6;"> 节点序号
            </label>
            <label style="display: flex; align-items: center; cursor: pointer;">
                <input type="checkbox" id="toggle-names" checked onchange="updateLabelStyles()" style="margin-right: 6px; accent-color: #3B82F6;"> 节点名称
            </label>
            <label style="display: flex; align-items: center; cursor: pointer;">
                <input type="checkbox" id="toggle-func" checked onchange="updateLabelStyles()" style="margin-right: 6px; accent-color: #00FFAA;"> 功能（分工）
            </label>
        </div>
    </div>

    <!-- 2.5 更新连线数据 -->
    <div style="margin-bottom: 18px; padding: 14px 16px; background: rgba(30, 41, 59, 0.85); border-radius: 10px; border: 1px solid rgba(51, 65, 85, 0.8);">
        <div style="font-size: 13px; font-weight: 600; color: #E2E8F0; margin-bottom: 10px;">🔗 更新连线数据</div>
        <input type="file" id="link-csv-input" accept=".csv" style="display: none;" onchange="updateLinkData(this)">
        <button onclick="document.getElementById('link-csv-input').click()" style="
            width: 100%; padding: 8px 12px; background: #0066FF; color: white; border: none;
            border-radius: 6px; font-size: 12px; font-weight: bold; cursor: pointer; margin-bottom: 6px;
        ">📂 选择 CSV 文件更新连线</button>
        <div id="link-update-status" style="font-size: 11px; color: #94A3B8; text-align: center;">当前: link_matrix_shanghai.csv</div>
    </div>

    <!-- 元素图例模块 -->
    <div style="background: rgba(30, 41, 59, 0.85); border-radius: 8px; padding: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); backdrop-filter: blur(8px);">
        <div style="color: #94A3B8; font-size: 13px; margin-bottom: 10px;">【元素图例】</div>
        <div style="display: flex; align-items: center; margin-bottom: 8px; font-size: 14px;">
            <div style="width: 12px; height: 12px; border-radius: 50%; border: 2px solid #FFF; background: #00FFAA; margin-right: 8px;"></div>
            <span style="color: #00FFAA; font-weight: bold; margin-right: 6px;">网络节点:</span> <span style="color: #E2E8F0;">桥隧空间静态拓扑点</span>
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 6px;">
             <div style="width: 24px; height: 3px; background: #0066FF; margin-right: 8px;"></div>
             <span style="color: #0066FF; font-weight: bold; margin-right: 6px;">路网连线:</span> <span style="color: #E2E8F0;">邻接路网直达拓扑路径</span>
        </div>
        <div style="display: flex; align-items: center; font-size: 14px; font-weight: bold;">
            <div style="width: 10px; height: 10px; border-radius: 50%; background: #EF4444; margin-right: 6px;"></div><span style="color: #EF4444; margin-right: 15px;">拥堵 (RED)</span>
            <div style="width: 10px; height: 10px; border-radius: 50%; background: #FACC15; margin-right: 6px;"></div><span style="color: #FACC15; margin-right: 15px;">缓行 (YELLOW)</span>
            <div style="width: 10px; height: 10px; border-radius: 50%; background: #10B981; margin-right: 6px;"></div><span style="color: #10B981;">畅通 (GREEN)</span>
        </div>
    </div>
</div>

<!-- 科技感折线图模态框 -->
<div id="chart-modal" style="display:none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 10000; background: rgba(15, 23, 42, 0.7); backdrop-filter: blur(8px); justify-content: center; align-items: center; opacity: 0; transition: opacity 0.3s;">
    <div style="background: #111827; border-radius: 12px; padding: 30px; width: 70%; min-width: 700px; box-shadow: 0 10px 40px rgba(0,0,0,0.5); position: relative;">
        <div onclick="closeChart()" style="position: absolute; top: 15px; right: 20px; color: #64748B; font-size: 28px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.color='#FFF'" onmouseout="this.style.color='#64748B'">&times;</div>
        <h2 id="chart-title" style="color: #FFFFFF; font-family: 'SF Pro Display', 'Microsoft YaHei', sans-serif; margin-top: 0; margin-bottom: 5px; text-align: center; letter-spacing: 1px; font-weight: 500;">Real-Time Forecast</h2>
        <div id="chart-subtitle" style="color: #94A3B8; text-align: center; font-size: 13px; margin-bottom: 20px;"></div>
        <div id="echarts-dom" style="width: 100%; height: 450px;"></div>
    </div>
</div>

<script>
    let isPredicting = false; 
    let currentStep = 0, playTimer = null;
    const forecastData = {forecast_data_json_str};
    const rawChartData = {chart_data_json_str};
    const bridgeInfo = {bridge_info_json};
    const nodeCoordsAll = {node_coords_json};

    // ---------------- 🌟 核心控制引擎：独立控制玻璃外壳的显隐 ----------------
    function updateLabelStyles() {{
        var showNodes = document.getElementById('toggle-nodes').checked;
        var showNames = document.getElementById('toggle-names').checked;
        var showFunc  = document.getElementById('toggle-func').checked;
        var styleHtml = "";

        if (!showNodes) styleHtml += ".bridge-node {{ display: none !important; }} ";
        if (!showNames) styleHtml += ".bridge-name {{ display: none !important; }} ";
        if (!showFunc)  styleHtml += ".bridge-func, .bridge-sep-func {{ display: none !important; }} ";

        // 分隔线：两边内容都没了才隐藏
        var leftHidden  = !showNodes;
        var rightHidden = !showNames && !showFunc;
        if (leftHidden || (!showNodes && !showNames)) {{
          styleHtml += ".bridge-separator:not(.bridge-sep-func) {{ display: none !important; }} ";
        }}

        // 若序号/名称/功能 全没了 → 整个 label 隐藏
        if (!showNodes && !showNames && !showFunc) {{
            styleHtml += ".label-text-container {{ display: none !important; }} ";
        }} else {{
            styleHtml += ".label-text-container {{ display: flex !important; }} ";
        }}

        document.getElementById('dynamic-label-styles').innerHTML = styleHtml;

        updateWrapperVisibility();
    }}

    function updateWrapperVisibility() {{
        var showNodes = document.getElementById('toggle-nodes').checked;
        var showNames = document.getElementById('toggle-names').checked;
        var showFunc  = document.getElementById('toggle-func').checked;
        var wrappers = document.querySelectorAll('.glass-label-wrapper');

        wrappers.forEach(el => {{
            if (!showNodes && !showNames && !showFunc && !isPredicting) {{
                el.style.display = 'none';
            }} else {{
                el.style.display = 'flex';
            }}
        }});
    }}

    if (forecastData && forecastData.total_steps > 0) {{
        document.getElementById('pred-slider').max = forecastData.total_steps - 1;
    }}

    function findStepIndexByDayTime(targetDay, targetHour) {{
        if (!forecastData || !forecastData.data) return -1;
        for (let i = 0; i < forecastData.data.length; i++) {{
            let timeStr = forecastData.data[i].forecast_time;
            let dt = new Date(timeStr.replace(/-/g, '/')); 
            let dDay = dt.getDay() === 0 ? 7 : dt.getDay();
            let dHour = dt.getHours();
            if (dDay == parseInt(targetDay) && dHour >= parseInt(targetHour)) return i;
        }}
        return 0; 
    }}

    function togglePrediction() {{
        const btn = document.getElementById('play-btn');
        const timeline = document.getElementById('pred-timeline-container');
        if (!forecastData || forecastData.total_steps === 0) return alert("⚠️ 未加载到有效推演数据，请确保存在 frontend_map_data.json。");

        isPredicting = !isPredicting;
        if (isPredicting) {{
            let selectedDay = document.getElementById('day-select').value;
            let selectedHour = document.getElementById('time-select').value;

            currentStep = findStepIndexByDayTime(selectedDay, selectedHour);
            if (currentStep === -1) currentStep = 0;
            document.getElementById('pred-slider').value = currentStep;

            btn.innerText = "⏸ 暂停推演";
            btn.style.background = "#10B981"; // 🌟 修复：恢复原来的绿色
            timeline.style.display = 'block';

            document.querySelectorAll('.dynamic-node').forEach(el => el.style.display = 'block');
            updateWrapperVisibility(); 
            document.querySelectorAll('.flow-badge-container').forEach(el => el.style.display = 'flex');

            startPredictionEngine();
        }} else {{
            btn.innerText = "▶ 启动 AI 预测引擎";
            btn.style.background = "#10B981";
            timeline.style.display = 'none';
            clearInterval(playTimer);

            document.querySelectorAll('.dynamic-node').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.flow-badge-container').forEach(el => el.style.display = 'none');

            updateWrapperVisibility(); 
        }}
    }}

    function startPredictionEngine() {{
        renderStep(currentStep);
        playTimer = setInterval(() => {{
            currentStep = (currentStep + 1) % forecastData.total_steps;
            document.getElementById('pred-slider').value = currentStep;
            renderStep(currentStep);
        }}, 1200);
    }}

    function onSliderChange() {{
        currentStep = parseInt(document.getElementById('pred-slider').value);
        renderStep(currentStep);
    }}

    function renderStep(stepIndex) {{
        if (!forecastData.data || !forecastData.data[stepIndex]) return;
        const stepInfo = forecastData.data[stepIndex];
        document.getElementById('pred-time-label').innerText = "预测推演时间: " + stepInfo.forecast_time;

        stepInfo.nodes.forEach(node => {{
            let uiDiv = document.getElementById('ui-node-' + node.node_id) || document.getElementById('ui-node-' + node.node_id.replace("Node_", ""));
            if (uiDiv) {{
                const dynamicDot = uiDiv.querySelector('.dynamic-node');
                const badgeContainer = uiDiv.querySelector('.flow-badge-container');
                const badgeText = uiDiv.querySelector('.flow-badge-text');

                let statusColor = '#10B981'; // 绿
                if (node.congestion_level === 'YELLOW') statusColor = '#F59E0B'; // 黄
                if (node.congestion_level === 'RED') statusColor = '#EF4444';    // 红

                dynamicDot.style.backgroundColor = statusColor;
                dynamicDot.style.boxShadow = `0 0 12px ${{statusColor}}`;

                badgeContainer.style.borderLeftColor = statusColor;
                badgeText.style.color = statusColor;
                badgeText.innerText = node.flow_pred.toFixed(1);
            }}
        }});
    }}

    // ---------------- 图表引擎 ----------------
    let myChart = null;

    function openChart(rawNodeId, nodeName, displayId, funcName, bridgeType, lanes, roadName, district) {{
        const modal = document.getElementById('chart-modal');
        modal.style.display = 'flex';
        setTimeout(() => modal.style.opacity = '1', 10);

        document.getElementById('chart-title').innerText = `Real-Time Forecast (Node ${{displayId}})`;

        // ---------- 用户要求：标题/副标题准确显示节点功能名称 ----------
        var subParts = [];
        if (nodeName)   subParts.push(`桥梁：${{nodeName}}`);
        if (funcName && funcName !== '-') subParts.push(`功能：${{funcName}}`);
        if (bridgeType && bridgeType !== '-') subParts.push(`类型：${{bridgeType}}`);
        if (lanes && lanes !== '-')      subParts.push(`车道：${{lanes}}`);
        if (roadName && roadName !== '-') subParts.push(`所属路：${{roadName}}`);
        if (district && district !== '-') subParts.push(`行政区：${{district}}`);
        document.getElementById('chart-subtitle').innerText = subParts.join('  ·  ');

        if (!myChart) myChart = echarts.init(document.getElementById('echarts-dom'));

        let dataObj = null;
        if (Array.isArray(rawChartData)) {{
            dataObj = rawChartData.find(item => item.node_id === rawNodeId || item.node_id === "Node_" + rawNodeId.replace("Node_", ""));
        }}

        let xAxisData = dataObj && dataObj.x_axis_times ? dataObj.x_axis_times : [];
        let pastData = dataObj && dataObj.series ? dataObj.series.history_data : [];
        let futureData = dataObj && dataObj.series ? dataObj.series.forecast_data : [];

        let splitIndex = 0;
        for (let i = 0; i < futureData.length; i++) {{
            if (futureData[i] !== null) {{
                splitIndex = i;
                break;
            }}
        }}

        const option = {{
            backgroundColor: 'transparent',
            tooltip: {{ 
                trigger: 'axis', 
                axisPointer: {{ type: 'line', lineStyle: {{ color: '#334155', type: 'dashed' }} }},
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: '#334155',
                textStyle: {{ color: '#F8FAFC' }}
            }},
            legend: {{ 
                data: ['Past Data', 'Forecast Data'], 
                textStyle: {{ color: '#CBD5E1', fontSize: 13 }}, 
                right: '5%', 
                top: '0%',
                icon: 'circle'
            }},
            grid: {{ left: '3%', right: '4%', bottom: '5%', containLabel: true }},
            xAxis: {{
                type: 'category', 
                boundaryGap: false, 
                data: xAxisData,
                axisLine: {{ lineStyle: {{ color: '#334155' }} }},
                axisLabel: {{ color: '#94A3B8', fontSize: 11 }},
                splitLine: {{ show: true, lineStyle: {{ color: '#1E293B', type: 'dashed' }} }}
            }},
            yAxis: {{
                type: 'value',
                axisLine: {{ show: false }}, 
                axisTick: {{ show: false }},
                axisLabel: {{ color: '#94A3B8' }},
                splitLine: {{ lineStyle: {{ color: '#1E293B', type: 'dashed' }} }}
            }},
            series: [
                {{
                    name: 'Past Data', 
                    type: 'line', 
                    smooth: false,
                    symbol: 'circle', 
                    symbolSize: 8,
                    itemStyle: {{ color: '#00F6FF' }}, 
                    lineStyle: {{ color: '#00F6FF', width: 2 }},
                    data: pastData,
                    markLine: {{
                        symbol: ['none', 'none'],
                        label: {{ show: false }},
                        lineStyle: {{ color: '#64748B', type: 'dashed', width: 2 }},
                        data: [ {{ xAxis: splitIndex }} ] 
                    }}
                }},
                {{
                    name: 'Forecast Data', 
                    type: 'line', 
                    smooth: false,
                    symbol: 'path://M-5,-5 L5,5 M-5,5 L5,-5', 
                    symbolSize: 10,
                    itemStyle: {{ color: '#38BDF8' }}, 
                    lineStyle: {{ color: '#38BDF8', width: 2, type: 'dashed' }},
                    data: futureData
                }}
            ]
        }};

        myChart.setOption(option, true);
    }}

    function closeChart() {{
        const modal = document.getElementById('chart-modal');
        modal.style.opacity = '0';
        setTimeout(() => modal.style.display = 'none', 300);
    }}

    window.addEventListener('resize', function() {{
        if(myChart) myChart.resize();
    }});

    window.onload = function() {{
        updateLabelStyles();
    }};

    // ---------------- 🔗 更新连线数据功能 ----------------
    function getActiveCoordSystem() {{
        var fgs = [
            {{ name: 'WGS84', fg: fg_wgs84 }},
            {{ name: 'GCJ02', fg: fg_gcj02 }},
            {{ name: 'BD09',  fg: fg_bd09  }}
        ];
        for (var i = 0; i < fgs.length; i++) {{
            if (map_49633a62c8e24e25a55b54a08e1367f9.hasLayer(fgs[i].fg)) return fgs[i].name;
        }}
        return 'GCJ02';
    }}

    function updateLinkData(input) {{
        var file = input.files[0];
        if (!file) return;

        var statusEl = document.getElementById('link-update-status');
        statusEl.textContent = '⏳ 正在解析...';
        statusEl.style.color = '#FACC15';

        var reader = new FileReader();
        reader.onload = function(e) {{
            try {{
                var text = e.target.result;
                var lines = text.trim().split('\\n');

                var nodeIdList = [];
                var weightMatrix = {{}};

                for (var i = 1; i < lines.length; i++) {{
                    var line = lines[i].trim();
                    if (!line) continue;
                    var parts = line.split(',');
                    var rowId = parseInt(parts[0].trim());
                    if (isNaN(rowId)) continue;
                    nodeIdList.push(rowId);
                    weightMatrix[rowId] = {{}};
                    for (var j = 1; j < parts.length; j++) {{
                        var colId = j - 1;
                        weightMatrix[rowId][colId] = parseFloat(parts[j].trim()) || 0;
                    }}
                }}

                var coordSys = getActiveCoordSystem();
                var coordKey = coordSys.toLowerCase();
                var newLayers = [];

                for (var ii = 0; ii < nodeIdList.length; ii++) {{
                    var nodeA = nodeIdList[ii];
                    for (var jj = 0; jj < nodeIdList.length; jj++) {{
                        var nodeB = nodeIdList[jj];
                        if (nodeA >= nodeB) continue;
                        var weight = weightMatrix[nodeA] ? weightMatrix[nodeA][nodeB] : 0;
                        if (!weight || weight <= 0) continue;

                        var coordsA = nodeCoordsAll[nodeA];
                        var coordsB = nodeCoordsAll[nodeB];
                        if (!coordsA || !coordsB) continue;

                        var nameA = bridgeInfo[nodeA] ? bridgeInfo[nodeA].name : ('Node ' + nodeA);
                        var nameB = bridgeInfo[nodeB] ? bridgeInfo[nodeB].name : ('Node ' + nodeB);

                        var latlngs = [
                            [coordsA[coordKey][0], coordsA[coordKey][1]],
                            [coordsB[coordKey][0], coordsB[coordKey][1]]
                        ];

                        var pl = L.polyline(latlngs, {{
                            color: '#0066FF', weight: 1.5, opacity: 0.6
                        }});
                        pl.bindTooltip('<b>网络连线</b><br>' + nameA + ' <-> ' + nameB + '<br>权重: ' + weight.toFixed(4));
                        pl._isLink = true;
                        newLayers.push({{ pl: pl, fg: coordSys }});
                    }}
                }}

                [fg_wgs84, fg_gcj02, fg_bd09].forEach(function(fg) {{
                    var toRemove = [];
                    fg.eachLayer(function(layer) {{
                        if (layer instanceof L.Polyline && !(layer instanceof L.Polygon)) toRemove.push(layer);
                    }});
                    toRemove.forEach(function(layer) {{ fg.removeLayer(layer); }});
                }});

                newLayers.forEach(function(item) {{
                    if (item.fg === 'WGS84') item.pl.addTo(fg_wgs84);
                    else if (item.fg === 'GCJ02') item.pl.addTo(fg_gcj02);
                    else if (item.fg === 'BD09') item.pl.addTo(fg_bd09);
                }});

                statusEl.textContent = '✅ 已更新: ' + file.name + ' (' + newLayers.length + '条连线)';
                statusEl.style.color = '#10B981';
                input.value = '';
            }} catch (err) {{
                statusEl.textContent = '❌ 解析失败: ' + err.message;
                statusEl.style.color = '#EF4444';
            }}
        }};
        reader.onerror = function() {{
            statusEl.textContent = '❌ 文件读取失败';
            statusEl.style.color = '#EF4444';
        }};
        reader.readAsText(file);
    }}
</script>
'''
m.get_root().html.add_child(folium.Element(html_injection))

m.save(output_html)
print(f"  ✅ 完美无瑕版地图已生成:\n     -> {output_html}")