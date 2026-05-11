<template>
  <div ref="mapRef" class="map"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch, computed } from "vue";
import * as Cesium from "cesium";

const props = defineProps({
  currentBridge: { type: Object, default: null },
  bridges: { type: Array, default: () => [] },
  modelUrl: { type: String, default: "" },
  showAllPoints: { type: Boolean, default: true },
  showAllLabels: { type: Boolean, default: true },
  showNodeIdx: { type: Boolean, default: true },
  mapMode: { type: String, default: "voyager" },
  showTopology: { type: Boolean, default: true },
  showLinkMatrix: { type: Boolean, default: true },
});

const emit = defineEmits(["bridge-click-with-index"]);

const mapRef = ref(null);
let viewer;
let tileset;
let markerEntity;
let bridgeEntities = [];
let topoEntities = [];   // 拓扑结构连线实体（NPY邻接矩阵的边）
let linkEntities = [];   // link_matrix 路网连线实体（CSV权重矩阵的边）
let gnnEdgeEntities = []; // GNN 可视化流量连线实体
let handler;
/* 连线显隐内部状态：props 仅提供初始值，之后由 setXxxVisible 单独控制，
   避免外部某一模块的开关去改 props 后反向影响其他模块的开关状态 */
const topologyVisible = ref(props.showTopology);
const linkMatrixVisible = ref(props.showLinkMatrix);
/* 记录：每个 bridge entity → { bridge, arrayIndex, node0Base } ，点击时能取到正确的 0 基 node 号 */
const entityMeta = new WeakMap();

/* 完全对齐 link_shanghai-1.py HTML 配色 */
const COLOR_GREEN = Cesium.Color.fromCssColorString("#10B981");   // 畅通 GREEN
const COLOR_YELLOW = Cesium.Color.fromCssColorString("#FACC15");  // 缓行 YELLOW
const COLOR_ORANGE = Cesium.Color.fromCssColorString("#F59E0B");  // 拥堵 ORANGE
const COLOR_RED = Cesium.Color.fromCssColorString("#EF4444");     // 拥堵 RED
const COLOR_CYAN = Cesium.Color.fromCssColorString("#00FFAA");    // 默认静态节点: 薄荷绿 (HTML COLOR_NODE = '#00FFAA')
const COLOR_LINK_DEFAULT = Cesium.Color.fromCssColorString("#38BDF8"); // 星空蓝 (HTML COLOR_EDGE)
const COLOR_LINK_GLOW = Cesium.Color.fromCssColorString("#0088FF"); // 折线图 PastData 色
const COLOR_LABEL_BG = Cesium.Color.fromCssColorString("rgba(255, 255, 255, 0.85)"); // 节点名称浅色玻璃背景（对齐图2）
const COLOR_LABEL_TEXT = Cesium.Color.fromCssColorString("#1A237E"); // 浅色玻璃背景上的深色文字

/* ============ 建立 node_0base → bridge 索引 ============
   ✅ 关键修复：即使 bridges 数组顺序被 ORDER BY id 打乱，我们依然能按 CSV 的 0 基 node 号正确找到对应桥！
   优先级：
   1) props.bridges 里存在 node_0base 字段 → 用 Map<node_0base, bridge> 精确匹配（最稳）
   2) 没有 node_0base 字段 → fallback 用 bridges 数组下标 i（假设后端 ORDER BY node_0base 已经排好序）
============================================================================= */
const node0BaseMap = computed(() => {
  const m = new Map();
  (props.bridges || []).forEach((b, arrayIndex) => {
    let k = b.node_0base != null ? Number(b.node_0base) : null;
    if (k == null || Number.isNaN(k)) k = Number(arrayIndex);
    m.set(k, { bridge: b, arrayIndex, node0Base: k });
  });
  return m;
});

/* ============ 节点坐标映射 (CSV node 0基 index -> lon/lat) ============
   双保险：先查 Map(node_0base)；找不到再 fallback bridges[arrayIndex]
============================================================================ */
function getBridgeIndexPosition(idx) {
  if (!props.bridges || props.bridges.length === 0) return null;
  const i = parseInt(idx, 10);
  if (!Number.isFinite(i) || i < 0) return null;
  const hit = node0BaseMap.value.get(i);
  if (hit) {
    const b = hit.bridge;
    let lon = Number(b.wgs_lon || b.lon);
    let lat = Number(b.wgs_lat || b.lat);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
    if (Math.abs(lon) <= 90 && Math.abs(lat) > 90 && Math.abs(lat) <= 180) {
      [lon, lat] = [lat, lon];
    }
    return { lon, lat, bridge: b, index: hit.arrayIndex, node0Base: hit.node0Base };
  }
  /* fallback：直接取下标（兼容没 reload_from_xlsx 的老库） */
  if (i >= props.bridges.length) return null;
  const b = props.bridges[i];
  if (!b) return null;
  let lon = Number(b.wgs_lon || b.lon);
  let lat = Number(b.wgs_lat || b.lat);
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
  if (Math.abs(lon) <= 90 && Math.abs(lat) > 90 && Math.abs(lat) <= 180) {
    [lon, lat] = [lat, lon];
  }
  return { lon, lat, bridge: b, index: i, node0Base: i };
}

/* ============ 绘制桥梁节点（完全对齐 link_shanghai HTML：薄荷绿+白外框） ============ */
function renderBridges() {
  if (!viewer) return;
  bridgeEntities.forEach((e) => viewer.entities.remove(e));
  bridgeEntities = [];
  entityMeta; /* <- 避免未使用 lint 警告 */
  (props.bridges || []).forEach((bridge, arrayIndex) => {
    let lon = Number(bridge.wgs_lon || bridge.lon);
    let lat = Number(bridge.wgs_lat || bridge.lat);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
    if (Math.abs(lon) <= 90 && Math.abs(lat) > 90 && Math.abs(lat) <= 180) {
      [lon, lat] = [lat, lon];
    }
    const node0Base =
      bridge.node_0base != null && !Number.isNaN(Number(bridge.node_0base))
        ? Number(bridge.node_0base)
        : Number(arrayIndex);
    const entity = viewer.entities.add({
      id: `bridge-${bridge.id}-${node0Base}`,
      name: bridge.name,
      position: Cesium.Cartesian3.fromDegrees(lon, lat, 20),
      point: {
        pixelSize: 12,
        color: COLOR_CYAN,
        outlineColor: Cesium.Color.WHITE,  // 对齐 HTML CircleMarker 白边
        outlineWidth: 0,                 // 对齐 HTML: weight=1.0
        heightReference: Cesium.HeightReference.NONE,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        show: props.showAllPoints,
      },
      label: {
        text: buildBridgeLabelText(bridge, node0Base),
        font: "12px sans-serif",
        fillColor: COLOR_LABEL_TEXT,
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 8,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        showBackground: false,
        backgroundColor: COLOR_LABEL_BG,
        backgroundPadding: new Cesium.Cartesian2(6, 3),
        pixelOffset: new Cesium.Cartesian2(0, -25),
        heightReference: Cesium.HeightReference.NONE,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        show: (labelCfg.value.showNodeIdx || labelCfg.value.showNodeName),
      },
    });
    bridgeEntities.push(entity);
    entityMeta.set(entity, { bridge, arrayIndex, node0Base });
  });
  /* 连线要在节点全部渲染后再画（因为连线依赖 node0BaseMap，而 node0BaseMap 依赖 bridges） */
  if (lastTopology.value) renderTopology(lastTopology.value);
}

/* ============ 加载拓扑连线 (link_matrix) ============ */
function renderTopology(topologyData) {
  if (!viewer) return;
  topoEntities.forEach((e) => viewer.entities.remove(e));
  topoEntities = [];
  if (!topologyData || !Array.isArray(topologyData.links)) return;
  lastTopology.value = topologyData;
  const { links } = topologyData;
  let rendered = 0, skipped = 0;
  console.log(
    `[Cesium] 绘制拓扑连线：共 ${links.length} 条 （对齐 HTML 科技蓝 #0066FF，weight>0）`
  );
  links.forEach((link) => {
    const s = getBridgeIndexPosition(link.source);
    const t = getBridgeIndexPosition(link.target);
    if (!s || !t) { skipped++; return; }
    rendered++;
    const w = Math.min(1, Math.max(0.05, link.weight));
    // 对齐 HTML: folium.PolyLine(color=COLOR_EDGE, weight=1.5, opacity=0.6)
    const thickness = 1.0 + w * 2.5;
    const color = COLOR_LINK_DEFAULT.withAlpha(0.45 + w * 0.25);
    const positions = Cesium.Cartesian3.fromDegreesArrayHeights([
      s.lon, s.lat, 18,
      t.lon, t.lat, 18,
    ]);
    const ent = viewer.entities.add({
      polyline: {
        positions,
        width: thickness,
        material: color,
        clampToGround: false,
        show: topologyVisible.value,
      },
    });
    topoEntities.push(ent);
  });
  console.log(`[Cesium]   成功绘制：${rendered} 条，跳过（没匹配到桥）：${skipped} 条`);
}

const lastTopology = ref(null);
/* 标签各部分独立显隐：序号 / 名称 由各自开关单独控制，
   当两部分都关闭时标签整体隐藏；任一开启即显示 */
const labelCfg = ref({ showNodeIdx: true, showNodeName: true, showFlowBadge: true });
watch(() => props.showNodeIdx, (v) => {
  labelCfg.value.showNodeIdx = v;
  renderBridges();
});
watch(() => props.showAllLabels, (v) => {
  labelCfg.value.showNodeName = v;
  renderBridges();
});
function buildBridgeLabelText(bridge, node0Base) {
  const parts = [];
  if (labelCfg.value.showNodeIdx) {
    const disp =
      bridge._displayIdx != null
        ? Number(bridge._displayIdx)
        : bridge.display_idx != null && !Number.isNaN(Number(bridge.display_idx))
          ? Number(bridge.display_idx)
          : Number(node0Base) + 1;
    parts.push(String(disp));
  }
  if (labelCfg.value.showNodeName) parts.push(bridge.name || "");
  if (labelCfg.value.showNodeIdx && labelCfg.value.showNodeName && parts.length === 2) {
    return `${parts[0]} | ${parts[1]}`;
  }
  return parts.join("");
}
function setLabelLayer(cfg) {
  if (cfg) {
    if ('showIndex' in cfg) cfg.showNodeIdx = cfg.showIndex;
    if ('showName' in cfg) cfg.showNodeName = cfg.showName;
  }
  Object.assign(labelCfg.value, cfg || {});
  renderBridges();
}

function setTopologyVisible(visible) {
  topologyVisible.value = visible;
  topoEntities.forEach((e) => {
    if (e.polyline) e.polyline.show = visible;
  });
}

/**
 * 设置路网连线（link_matrix CSV）的可见性
 * @param {boolean} visible - 是否显示路网连线
 */
function setLinkMatrixVisible(visible) {
  linkMatrixVisible.value = visible;
  // 拓扑连线与路网连线均来自 link_matrix CSV，开关统一控制
  topoEntities.forEach((e) => {
    if (e.polyline) e.polyline.show = visible;
  });
  linkEntities.forEach((e) => {
    if (e.polyline) e.polyline.show = visible;
  });
}

/**
 * 渲染路网连线（来自 link_matrix CSV 权重矩阵）
 * 使用琥珀色区别于拓扑连线（星空蓝）
 * @param {Array} edges - 边数组 [{source, target, weight}]
 * @param {Array} bridges - 桥梁数组，需含 lon/lat
 */
function renderLinkMatrix(edges, bridges) {
  // 清除旧的路网连线
  linkEntities.forEach((e) => {
    try {
      viewer.entities.remove(e);
    } catch (_err) {
      /* ignore */
    }
  });
  linkEntities.length = 0;

  if (!edges || edges.length === 0) {
    console.log("[CesiumMap] renderLinkMatrix: 无路网边数据");
    return;
  }
  if (!bridges || bridges.length === 0) {
    console.log("[CesiumMap] renderLinkMatrix: 无桥梁节点数据");
    return;
  }

  // 建立 node0Base → bridge 的映射（与 renderTopology 相同逻辑）
  // 同时用数组索引和 node_0base 两种 key 建映射，兼容不同数据源
  const nodeMap = new Map();
  bridges.forEach((b, arrayIndex) => {
    // 用 node_0base 建映射（强制转 Number 避免类型不匹配）
    if (b.node_0base != null) {
      const key = Number(b.node_0base);
      if (Number.isFinite(key)) nodeMap.set(key, b);
    }
    if (b.node0Base != null) {
      const key = Number(b.node0Base);
      if (Number.isFinite(key)) nodeMap.set(key, b);
    }
    // 用数组索引建映射（兜底，edge 的 source/target 可能是 CSV 行号）
    nodeMap.set(arrayIndex, b);
  });

  let drawn = 0;
  edges.forEach((edge) => {
    const src = nodeMap.get(Number(edge.source));
    const tgt = nodeMap.get(Number(edge.target));
    if (!src || !tgt) return;
    const sLon = src.wgs_lon ?? src.lon ?? src.x;
    const sLat = src.wgs_lat ?? src.lat ?? src.y;
    const tLon = tgt.wgs_lon ?? tgt.lon ?? tgt.x;
    const tLat = tgt.wgs_lat ?? tgt.lat ?? tgt.y;
    if (sLon == null || sLat == null || tLon == null || tLat == null) return;

    // 线宽根据权重调整（权重越大线越粗）
    const weight = edge.weight ?? 1.0;
    const lineWidth = Math.max(1.2, Math.min(3.5, 1.2 + weight * 2.5));

    const entity = viewer.entities.add({
      polyline: {
        positions: Cesium.Cartesian3.fromDegreesArrayHeights([
          Number(sLon), Number(sLat), 20,
          Number(tLon), Number(tLat), 20,
        ]),
        width: lineWidth,
        material: Cesium.Color.fromCssColorString("#0066FF").withAlpha(0.6),
        show: linkMatrixVisible.value,
      },
    });
    linkEntities.push(entity);
    drawn++;
  });

  console.log(`[CesiumMap] renderLinkMatrix: 桥梁${bridges.length}个, nodeMap keys=${nodeMap.size}, 绘制 ${drawn}/${edges.length} 条路网连线`);
}

/* ============ 推演结果可视化：节点着色 + 流量连线动画 ============ */
function updateInferenceVisualization({ stepData, nodeIds, stepIndex, totalSteps }) {
  if (!viewer) return;
  const step = stepData;
  const nodes = step.nodes || [];
  // 关键：严格按数组下标对齐 (Node_0 -> 下标0, Node_1 -> 下标1, ...)
  const nodeMap = new Map(nodes.map((n) => {
    const key = String(n.node_id).replace("Node_", "");
    return [parseInt(key, 10), n];
  }));

  gnnEdgeEntities.forEach((e) => viewer.entities.remove(e));
  gnnEdgeEntities = [];

  let redN = 0, orangeN = 0, greenN = 0;

  // bridgeEntities 的 push 顺序 === props.bridges 遍历顺序，所以直接按数组下标对应
  bridgeEntities.forEach((entity, arrayIdx) => {
    const nodeObj = nodeMap.get(arrayIdx);
    if (!nodeObj) {
      entity.point.color = COLOR_CYAN;
      entity.point.pixelSize = 12;
      const bridge = props.bridges[arrayIdx];
      entity.label.text = bridge?.name || "";
      entity.label.fillColor = COLOR_LABEL_TEXT;
      entity.label.outlineColor = Cesium.Color.WHITE;
      entity.label.show = (labelCfg.value.showNodeIdx || labelCfg.value.showNodeName);
      return;
    }
    const flow = parseFloat(nodeObj.flow_pred);
    let color;
    // 严格对齐 link_shanghai HTML renderStep 分级
    const lvl = nodeObj.congestion_level || (flow >= 1200 ? "RED" : (flow >= 600 ? "YELLOW" : "GREEN"));
    if (lvl === "RED") { color = COLOR_RED; redN++; }
    else if (lvl === "YELLOW") { color = COLOR_YELLOW; orangeN++; }  // 用 HTML 的亮琥珀黄
    else { color = COLOR_GREEN; greenN++; }
    entity.point.color = color.withAlpha(1.0);
    entity.point.pixelSize = 12;
    entity.point.outlineColor = Cesium.Color.WHITE;
    entity.point.outlineWidth = 0;
    entity.label.text = `${flow.toFixed(0)} 辆/h`;
    entity.label.fillColor = color;
    entity.label.outlineColor = Cesium.Color.BLACK;
    entity.label.outlineWidth = 2;
    entity.label.showBackground = false;
    entity.label.backgroundColor = COLOR_LABEL_BG;
    entity.label.backgroundPadding = new Cesium.Cartesian2(6, 3);
    entity.label.show = true;
  });


  console.log(`[Inference Step ${stepIndex + 1}/${totalSteps}] R=${redN} O=${orangeN} G=${greenN} Flow-links=${gnnEdgeEntities.length}`);
}

/* ============ 重置视图状态到默认 ============ */
function resetVisualization() {
  if (!viewer) return;
  gnnEdgeEntities.forEach((e) => viewer.entities.remove(e));
  gnnEdgeEntities = [];

  // 清除路网连线
  linkEntities.forEach((e) => {
    try {
      viewer.entities.remove(e);
    } catch (_err) {
      /* ignore */
    }
  });
  linkEntities.length = 0;

  bridgeEntities.forEach((entity, arrayIdx) => {
    entity.point.color = COLOR_CYAN;
    entity.point.pixelSize = 12;
    const bridge = props.bridges[arrayIdx];
    entity.label.text = bridge?.name || "";
    entity.label.fillColor = COLOR_LABEL_TEXT;
    entity.label.outlineColor = Cesium.Color.WHITE;
    entity.label.show = (labelCfg.value.showNodeIdx || labelCfg.value.showNodeName);
  });
}
/* 新增：上海桥隧蔓延模型专用高亮与重置 */
function highlightSpreadNode(nodeId) {
  if (nodeId == null || !viewer) return;
  const targetNode0 = Number(nodeId);

  for (let i = 0; i < bridgeEntities.length; i++) {
    const entity = bridgeEntities[i];
    const meta = entityMeta.get(entity);
    const node0 = meta ? meta.node0Base : Number(entity.id.split("-")[2]);

    if (node0 === targetNode0) {
      if (entity.point) {
        entity.point.color = COLOR_RED;
        entity.point.pixelSize = 12;
      }
      break;
    }
  }
}

function resetSpreadVisualization() {
  if (!viewer) return;
  bridgeEntities.forEach((entity) => {
    if (entity.point) {
      entity.point.color = COLOR_CYAN;
      entity.point.pixelSize = 12;
    }
  });
}

function updateMapMode(mode) {
  if (!viewer) return;
  const layers = viewer.imageryLayers;
  layers.removeAll();
  switch (mode) {
    case "satellite":
      layers.addImageryProvider(
        new Cesium.UrlTemplateImageryProvider({
          url: "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          credit: new Cesium.Credit("Esri, Maxar, Earthstar Geographics"),
        })
      );
      break;
    case "street":
      layers.addImageryProvider(
        new Cesium.OpenStreetMapImageryProvider({
          url: "https://tile.openstreetmap.org/",
        })
      );
      break;
    case "dark":
      layers.addImageryProvider(
        new Cesium.UrlTemplateImageryProvider({
          url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
          subdomains: ["a", "b", "c", "d"],
          credit: new Cesium.Credit("CartoDB"),
        })
      );
      break;
    case "light":
      layers.addImageryProvider(
        new Cesium.UrlTemplateImageryProvider({
          url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
          subdomains: ["a", "b", "c", "d"],
          credit: new Cesium.Credit("CartoDB"),
        })
      );
      break;

    case "voyager":
      layers.addImageryProvider(
        new Cesium.UrlTemplateImageryProvider({
          url: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
          subdomains: ["a", "b", "c", "d"],
          credit: new Cesium.Credit("CartoDB"),
        })
      );
      break;

    default:
      layers.addImageryProvider(
        new Cesium.UrlTemplateImageryProvider({
          url: "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          credit: new Cesium.Credit("Esri, Maxar, Earthstar Geographics"),
        })
      );
  }
}

onMounted(() => {
  viewer = new Cesium.Viewer(mapRef.value, {
    baseLayer: false,
    terrainProvider: new Cesium.EllipsoidTerrainProvider(),
    timeline: false,
    animation: false,
    geocoder: false,
    homeButton: false,
    baseLayerPicker: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    fullscreenButton: false,
    infoBox: false,
    selectionIndicator: false,
  });
  updateMapMode(props.mapMode);
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(121.4737, 31.2304, 25000),
    orientation: {
      heading: Cesium.Math.toRadians(0),
      pitch: Cesium.Math.toRadians(-70),
      roll: 0.0,
    },
  });
  viewer.scene.globe.enableLighting = false;
  viewer.scene.skyAtmosphere.show = true;
  viewer.scene.globe.depthTestAgainstTerrain = false;

  handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
  handler.setInputAction((movement) => {
    const picked = viewer.scene.pick(movement.position);
    if (picked && picked.id) {
      const ent = picked.id;
      if (ent && typeof ent === "object" && ent.id && String(ent.id).startsWith("bridge-")) {
        const meta = entityMeta.get(ent);
        if (meta) {
          emit("bridge-click-with-index", {
            bridge: meta.bridge,
            arrayIndex: meta.arrayIndex,
            node0Base: meta.node0Base,
            entity: ent,
          });
          return;
        }
        const idStr = String(ent.id);
        const parts = idStr.split("-");
        const bid = parseInt(parts[1], 10);
        const bridge = props.bridges.find((b) => String(b.id) === String(bid));
        if (bridge) {
          const idx = props.bridges.findIndex((b) => b.id === bridge.id);
          emit("bridge-click-with-index", {
            bridge,
            arrayIndex: idx >= 0 ? idx : 0,
            node0Base: idx >= 0 ? idx : -1,
            entity: ent,
          });
        }
        return;
      }
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  renderBridges();
});

onBeforeUnmount(() => {
  try {
    if (handler) handler.destroy();
    if (viewer && !viewer.isDestroyed()) viewer.destroy();
  } catch (_e) {}
});

function flyToBridge(bridge, height = 1200) {
  if (!viewer || !bridge) return;
  let lon = Number(bridge.wgs_lon || bridge.lon);
  let lat = Number(bridge.wgs_lat || bridge.lat);
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;
  if (Math.abs(lon) <= 90 && Math.abs(lat) > 90 && Math.abs(lat) <= 180) {
    [lon, lat] = [lat, lon];
  }
  const position = Cesium.Cartesian3.fromDegrees(lon, lat, 20);
  if (markerEntity) viewer.entities.remove(markerEntity);
  markerEntity = viewer.entities.add({
    name: "当前选中",
    position,
    point: {
      pixelSize: 16,
      color: Cesium.Color.YELLOW.withAlpha(0.95),
      outlineWidth: 0,
      heightReference: Cesium.HeightReference.NONE,
      show: true,
    },
  });
  bridgeEntities.forEach((e) => {
    e.label.show = (labelCfg.value.showNodeIdx || labelCfg.value.showNodeName);
    e.point.show = props.showAllPoints;
  });
  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(lon, lat, height),
  });
}

/* =================== 兼容两种推演数据格式 ===================
   格式 A (旧 GnnDeduction): { nodes: { "QJ0001": 0~100 负载率, ... } }
   格式 B (新 inference.py): { nodes: [ {node_id:"Node_0", flow_pred:number} ] }
============================================================= */
function updateGnnVisualization(stepDataRawOrWrapperObj) {
  if (!viewer) return;
  const stepData = stepDataRawOrWrapperObj?.stepData ?? stepDataRawOrWrapperObj;
  const stepIndex = stepDataRawOrWrapperObj?.stepIndex ?? 0;
  const totalSteps = stepDataRawOrWrapperObj?.totalSteps ?? 1;

  if (Array.isArray(stepData.nodes)) {
    return updateInferenceVisualization({ stepData, stepIndex, totalSteps });
  }
  const nodesObj = stepData.nodes || {};
  gnnEdgeEntities.forEach((e) => viewer.entities.remove(e));
  gnnEdgeEntities = [];
  let redN = 0, orangeN = 0, greenN = 0;
  bridgeEntities.forEach((entity, arrayIdx) => {
    const bridge = props.bridges[arrayIdx];
    let load = null;
    if (bridge && nodesObj[bridge.code] !== undefined) load = parseFloat(nodesObj[bridge.code]);
    else if (bridge && nodesObj[bridge.id] !== undefined) load = parseFloat(nodesObj[bridge.id]);
    if (load === null || !Number.isFinite(load)) {
      entity.point.color = COLOR_CYAN;
      entity.point.pixelSize = 12;
      entity.label.text = bridge?.name || "";
      entity.label.fillColor = COLOR_LABEL_TEXT;
      entity.label.outlineColor = Cesium.Color.WHITE;
      entity.label.show = (labelCfg.value.showNodeIdx || labelCfg.value.showNodeName);
      return;
    }
    let color;
    if (load >= 60) { color = COLOR_RED; redN++; }
    else if (load >= 30) { color = COLOR_ORANGE; orangeN++; }
    else { color = COLOR_GREEN; greenN++; }
    entity.point.color = color.withAlpha(1.0);
    entity.point.pixelSize = 12;
    entity.label.text = `${load.toFixed(1)} %`;
    entity.label.fillColor = color;
    entity.label.outlineColor = Cesium.Color.BLACK;
    entity.label.outlineWidth = 2;
    entity.label.showBackground = true;
    entity.label.backgroundColor = COLOR_LABEL_BG;
    entity.label.backgroundPadding = new Cesium.Cartesian2(6, 3);
    entity.label.show = true;
  });
  console.log(`[GNN 旧模式] R=${redN} O=${orangeN} G=${greenN}`);
}



defineExpose({
  highlightSpreadNode,
  resetSpreadVisualization,
  flyToBridge,
  updateGnnVisualization,
  updateInferenceVisualization,
  renderTopology,
  setTopologyVisible,
  renderLinkMatrix,
  setLinkMatrixVisible,
  resetVisualization,
  setLabelLayer,
  viewer,
});

watch(
  () => props.bridges,
  () => renderBridges(),
  { deep: true }
);
watch(() => props.showAllPoints, (val) => bridgeEntities.forEach((e) => (e.point.show = val)));
watch(() => props.mapMode, (val) => updateMapMode(val));
watch(() => props.showTopology, (val) => setTopologyVisible(val));
// props 仅作为初始值来源；运行中由各模块独立开关（setLinkMatrixVisible）控制显隐，
// props 变化只做一次性同步，不反向影响各模块自身开关状态
watch(() => props.showLinkMatrix, (val) => setLinkMatrixVisible(val));
watch(
  () => props.currentBridge,
  async (bridge) => {
    if (!viewer || !bridge) return;
    flyToBridge(bridge, 1500);
  }
);
watch(
  () => props.modelUrl,
  async (url) => {
    if (!viewer || !url) return;
    if (tileset) viewer.scene.primitives.remove(tileset);
    tileset = await Cesium.Cesium3DTileset.fromUrl(url);
    viewer.scene.primitives.add(tileset);
    viewer.zoomTo(tileset);
  }
);
</script>

<style scoped>
.map {
  width: 100%;
  height: 100%;
}
</style>
