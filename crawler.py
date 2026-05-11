import requests
import pandas as pd
import json
import time
import os
import math

# 高德地图 API 配置
AMAP_KEY = "3113f556d727b3e66680a873eabba494"
CITY_NAME = "上海"
TYPES = "190300"  # 190300 是交通地名总类，包含桥梁、隧道、立交桥等

# GCJ-02 to WGS84 转换逻辑
PI = 3.1415926535897932384626
A = 6378245.0
EE = 0.00669342162296594323

def transform_lat(x, y):
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * PI) + 40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * PI) + 320 * math.sin(y * PI / 30.0)) * 2.0 / 3.0
    return ret

def transform_lon(x, y):
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * PI) + 40.0 * math.sin(x / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * PI) + 300.0 * math.sin(x / 30.0 * PI)) * 2.0 / 3.0
    return ret

def gcj02_to_wgs84(lng, lat):
    dlat = transform_lat(lng - 105.0, lat - 35.0)
    dlng = transform_lon(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    mglat = lat + dlat
    mglng = lng + dlng
    return [lng * 2 - mglng, lat * 2 - mglat]

def fetch_poi(city, types, key):
    all_pois = []
    # 专注于桥梁，分层次搜索确保大桥不被遗漏
    search_configs = [
        {"keywords": "杨浦大桥|南浦大桥|卢浦大桥|徐浦大桥|闵浦大桥", "types": "190300"}, # 核心大桥
        {"keywords": "大桥|立交桥|桥", "types": "190300|190301|190306|190307"} # 桥梁相关
    ]
    
    seen_ids = set()
    for config in search_configs:
        page = 1
        while True:
            url = f"https://restapi.amap.com/v3/place/text?key={key}&keywords={config['keywords']}&types={config['types']}&city={city}&children=1&offset=20&page={page}&extensions=all"
            try:
                response = requests.get(url)
                data = response.json()
                if data['status'] == '1' and int(data['count']) > 0:
                    pois = data['pois']
                    if not pois:
                        break
                    
                    added_in_page = 0
                    for poi in pois:
                        if poi['id'] not in seen_ids:
                            all_pois.append(poi)
                            seen_ids.add(poi['id'])
                            added_in_page += 1
                    
                    print(f"Fetched {config['keywords']} page {page}, added {added_in_page} new POIs, total {len(all_pois)}")
                    
                    if added_in_page == 0 and page > 1: # 连续两页没新数据就停
                        break
                        
                    page += 1
                    if page > 50:
                        break
                    time.sleep(0.05)
                else:
                    break
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break
    return all_pois

def process_pois(pois):
    processed = []
    seen_codes = set()
    for poi in pois:
        code = poi.get('id', '')
        if code in seen_codes:
            continue
            
        name = poi.get('name', '')
        
        # 严格过滤逻辑：
        # 1. 必须包含“桥”字
        if '桥' not in name:
            continue
            
        # 2. 清洗掉包含“路”、“街”、“弄”、“大道”、“高速”字样的纯道路数据
        # 但是如果包含“大桥”、“立交桥”、“跨线桥”，则认为是我们要的桥梁设施，保留
        if any(road_word in name for road_word in ['路', '街', '弄', '大道', '高速']):
            if not any(keep_word in name for keep_word in ['大桥', '立交桥', '跨线桥']):
                continue
            
        location = poi.get('location', '0,0').split(',')
        lng = float(location[0])
        lat = float(location[1])
        wgs_coords = gcj02_to_wgs84(lng, lat)
        
        processed.append({
            'code': code,
            'name': name,
            'district': poi.get('adname', ''),
            'bridge_type': poi.get('type', '').split(';')[-1],
            'description': poi.get('address', ''),
            'lon': lng,
            'lat': lat,
            'wgs_lon': wgs_coords[0],
            'wgs_lat': wgs_coords[1],
            'address': poi.get('address', '')
        })
        seen_codes.add(code)
    return processed

def save_to_excel(data, filename="shanghai_bridges_tunnels.xlsx"):
    df = pd.DataFrame(data)
    df.to_excel(filename, index=False)
    print(f"Saved {len(data)} records to {filename}")

def update_database(data):
    sql_file = "update_pois.sql"
    with open(sql_file, "w", encoding="utf-8") as f:
        # 首先清理旧数据，确保只保留本次爬取的桥隧数据
        f.write("TRUNCATE TABLE bridges;\n")
        for item in data:
            sql = f"INSERT INTO bridges (code, name, district, bridge_type, description, lon, lat, wgs_lon, wgs_lat) " \
                  f"VALUES ('{item['code']}', '{item['name']}', '{item['district']}', '{item['bridge_type']}', '{item['description']}', {item['lon']}, {item['lat']}, {item['wgs_lon']}, {item['wgs_lat']}) " \
                  f"ON CONFLICT (code) DO NOTHING;\n"
            f.write(sql)
    print(f"Generated SQL file: {sql_file}")

if __name__ == "__main__":
    print("Starting to fetch POIs from Amap...")
    raw_pois = fetch_poi(CITY_NAME, TYPES, AMAP_KEY)
    if raw_pois:
        processed_data = process_pois(raw_pois)
        print(f"Processed {len(processed_data)} valid POIs")
        # 检查是否包含杨浦大桥
        names = [item['name'] for item in processed_data]
        if any('杨浦大桥' in n for n in names):
            print("Found 杨浦大桥!")
        else:
            print("杨浦大桥 not found in processed data.")
            
        save_to_excel(processed_data)
        update_database(processed_data)
        print("Data processing completed.")
    else:
        print("No POIs found or error occurred.")
