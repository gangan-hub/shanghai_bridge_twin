// 坐标转换：支持常见中国互联网坐标系纠偏
// - WGS84：Cesium 原生地球坐标（经纬度）
// - GCJ-02：高德/腾讯/国测局“火星坐标”
// - BD-09：百度坐标
//
// 说明：GCJ/BD 转 WGS84 属于近似反算，满足地图定位/展示精度需求（米级）。

const PI = Math.PI;
const A = 6378245.0;
const EE = 0.00669342162296594323;

function outOfChina(lon, lat) {
  // 中国大陆大致范围外不做偏移
  return lon < 72.004 || lon > 137.8347 || lat < 0.8293 || lat > 55.8271;
}

function transformLat(x, y) {
  let ret =
    -100.0 +
    2.0 * x +
    3.0 * y +
    0.2 * y * y +
    0.1 * x * y +
    0.2 * Math.sqrt(Math.abs(x));
  ret += ((20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0) / 3.0;
  ret += ((20.0 * Math.sin(y * PI) + 40.0 * Math.sin((y / 3.0) * PI)) * 2.0) / 3.0;
  ret += ((160.0 * Math.sin((y / 12.0) * PI) + 320 * Math.sin((y * PI) / 30.0)) * 2.0) / 3.0;
  return ret;
}

function transformLon(x, y) {
  let ret =
    300.0 +
    x +
    2.0 * y +
    0.1 * x * x +
    0.1 * x * y +
    0.1 * Math.sqrt(Math.abs(x));
  ret += ((20.0 * Math.sin(6.0 * x * PI) + 20.0 * Math.sin(2.0 * x * PI)) * 2.0) / 3.0;
  ret += ((20.0 * Math.sin(x * PI) + 40.0 * Math.sin((x / 3.0) * PI)) * 2.0) / 3.0;
  ret += ((150.0 * Math.sin((x / 12.0) * PI) + 300.0 * Math.sin((x / 30.0) * PI)) * 2.0) / 3.0;
  return ret;
}

export function wgs84ToGcj02(lon, lat) {
  if (outOfChina(lon, lat)) return { lon, lat };
  let dLat = transformLat(lon - 105.0, lat - 35.0);
  let dLon = transformLon(lon - 105.0, lat - 35.0);
  const radLat = (lat / 180.0) * PI;
  let magic = Math.sin(radLat);
  magic = 1 - EE * magic * magic;
  const sqrtMagic = Math.sqrt(magic);
  dLat = (dLat * 180.0) / (((A * (1 - EE)) / (magic * sqrtMagic)) * PI);
  dLon = (dLon * 180.0) / ((A / sqrtMagic) * Math.cos(radLat) * PI);
  const mgLat = lat + dLat;
  const mgLon = lon + dLon;
  return { lon: mgLon, lat: mgLat };
}

export function gcj02ToWgs84(lon, lat) {
  if (outOfChina(lon, lat)) return { lon, lat };
  // 迭代/近似反解：wgs = gcj - (gcj(wgs)-wgs)
  const g = wgs84ToGcj02(lon, lat);
  const dLon = g.lon - lon;
  const dLat = g.lat - lat;
  return { lon: lon - dLon, lat: lat - dLat };
}

export function bd09ToGcj02(lon, lat) {
  const x = lon - 0.0065;
  const y = lat - 0.006;
  const z = Math.sqrt(x * x + y * y) - 0.00002 * Math.sin(y * PI);
  const theta = Math.atan2(y, x) - 0.000003 * Math.cos(x * PI);
  return { lon: z * Math.cos(theta), lat: z * Math.sin(theta) };
}

export function gcj02ToBd09(lon, lat) {
  const z = Math.sqrt(lon * lon + lat * lat) + 0.00002 * Math.sin(lat * PI);
  const theta = Math.atan2(lat, lon) + 0.000003 * Math.cos(lon * PI);
  return { lon: z * Math.cos(theta) + 0.0065, lat: z * Math.sin(theta) + 0.006 };
}

export function bd09ToWgs84(lon, lat) {
  const gcj = bd09ToGcj02(lon, lat);
  return gcj02ToWgs84(gcj.lon, gcj.lat);
}

export function convertToWgs84(lon, lat, source) {
  const s = String(source || "wgs84").toLowerCase();
  if (s === "wgs84" || s === "epsg:4326") return { lon, lat };
  if (s === "gcj02" || s === "gcj-02") return gcj02ToWgs84(lon, lat);
  if (s === "bd09" || s === "bd-09") return bd09ToWgs84(lon, lat);
  return { lon, lat };
}

