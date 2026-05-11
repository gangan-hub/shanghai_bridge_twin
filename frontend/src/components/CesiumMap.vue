<template>
  <div ref="mapRef" class="map"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as Cesium from "cesium";

const props = defineProps({
  currentBridge: { type: Object, default: null },
  bridges: { type: Array, default: () => [] },
  modelUrl: { type: String, default: "" },
  pickMode: { type: Boolean, default: false },
  showAllPoints: { type: Boolean, default: true },
  showAllLabels: { type: Boolean, default: true },
  mapMode: { type: String, default: "satellite" },
});

const emit = defineEmits(["picked"]);

const mapRef = ref(null);
let viewer;
let tileset;
let markerEntity;
let bridgeEntities = [];
let gnnEdges = [];
let handler;

// 绘制 GNN 推演结果（节点变色与流量数值显示）
function updateGnnVisualization(stepData) {
  if (!viewer) return;
  
  const { nodes } = stepData;
  console.log("Updating GNN Visualization step:", stepData.step);

  // 1. 更新所有节点颜色和标签
  bridgeEntities.forEach(entity => {
    const bridgeId = entity.id.split('-')[1];
    const bridge = props.bridges.find(b => String(b.id) === String(bridgeId));
    
    if (bridge && nodes[bridge.code] !== undefined) {
      const load = nodes[bridge.code]; // 0-100 负载比例
      const flowValue = (load * 2.5).toFixed(0); 
      
      // 定义更好看的颜色
      const colorGreen = Cesium.Color.fromCssColorString("#10b981"); // 翡翠绿，更现代
      const colorOrange = Cesium.Color.fromCssColorString("#f59e0b"); // 琥珀橙
      const colorRed = Cesium.Color.fromCssColorString("#ef4444"); // 珊瑚红

      let color;
      if (flowValue >= 60) {
        color = colorRed;
      } else if (flowValue >= 30) {
        color = colorOrange;
      } else {
        color = colorGreen;
      }
      
      // 更新点位颜色和大小
      entity.point.color = color.withAlpha(1.0);
      entity.point.pixelSize = 14 + (load / 10);
      entity.point.outlineWidth = 0; // 确保推演时也没有描边
      
      // 节点字只显示数值和单位 (辆/5分)
      entity.label.text = `${flowValue} 辆/5分`;
      entity.label.fillColor = color;
      entity.label.outlineColor = Cesium.Color.BLACK;
      entity.label.outlineWidth = 2;
      entity.label.showBackground = false; 
      entity.label.show = true; 
    } else {
      // 非推演状态，恢复默认
      entity.point.color = Cesium.Color.CYAN.withAlpha(0.9);
      entity.point.pixelSize = 12;
      entity.label.text = bridge?.name || "";
      entity.label.fillColor = Cesium.Color.WHITE;
      entity.label.showBackground = false; // 默认也是透明
      entity.label.show = props.showAllLabels;
    }
  });

  // 2. 清除所有连线（根据用户要求移除连线）
  gnnEdges.forEach(e => viewer.entities.remove(e));
  gnnEdges = [];
}

// 切换地图模式
function updateMapMode(mode) {
  if (!viewer) return;
  viewer.imageryLayers.removeAll(true);

  let provider;
  let showLabels = false;

  switch (mode) {
    case "satellite":
      provider = new Cesium.UrlTemplateImageryProvider({
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        credit: "Tiles © Esri",
        maximumLevel: 19,
      });
      showLabels = true; // 卫星图需要叠加地名标注
      break;
    case "street":
      provider = new Cesium.UrlTemplateImageryProvider({
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        credit: "Tiles © Esri",
        maximumLevel: 19,
      });
      break;
    case "dark":
      // 极夜黑科技感底图 - 使用 CartoDB 的 Dark Matter，更专业且自带道路信息
      provider = new Cesium.UrlTemplateImageryProvider({
        url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        credit: "© OpenStreetMap contributors, © CARTO",
        subdomains: "abcd",
        maximumLevel: 20,
      });
      break;
    case "light":
      provider = new Cesium.UrlTemplateImageryProvider({
        url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        credit: "© OpenStreetMap contributors, © CARTO",
        subdomains: "abcd",
        maximumLevel: 19,
      });
      break;
    default:
      provider = new Cesium.UrlTemplateImageryProvider({
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        credit: "Tiles © Esri",
      });
      showLabels = true;
  }

  viewer.imageryLayers.addImageryProvider(provider);

  if (showLabels) {
    const worldLabels = new Cesium.UrlTemplateImageryProvider({
      url: "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      credit: "Labels © Esri",
      maximumLevel: 19,
    });
    viewer.imageryLayers.addImageryProvider(worldLabels);
  }
}

// 渲染所有桥梁标记
function renderBridges() {
  if (!viewer) return;
  console.log("Rendering bridges, count:", props.bridges.length);
  // 清理旧标记
  bridgeEntities.forEach((e) => viewer.entities.remove(e));
  bridgeEntities = [];

  props.bridges.forEach((bridge) => {
    // 优先使用 WGS84 坐标
    let lon = Number(bridge.wgs_lon || bridge.lon);
    let lat = Number(bridge.wgs_lat || bridge.lat);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      console.warn("Invalid coordinates for bridge:", bridge.name, lon, lat);
      return;
    }

    // 兜底纠偏
    if (Math.abs(lon) <= 90 && Math.abs(lat) > 90 && Math.abs(lat) <= 180) {
      [lon, lat] = [lat, lon];
    }

    const isCurrent = props.currentBridge && props.currentBridge.id === bridge.id;

    const entity = viewer.entities.add({
      id: `bridge-${bridge.id}`,
      name: bridge.name,
      position: Cesium.Cartesian3.fromDegrees(lon, lat, 10),
      point: {
        pixelSize: 12, // 增大一点
        color: Cesium.Color.CYAN.withAlpha(0.9), // 亮青色，更明显
        outlineWidth: 0, // 移除描边
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY, // 确保永远在最前
        show: props.showAllPoints,
      },
      label: {
        text: bridge.name,
        font: "12px sans-serif",
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 2,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        showBackground: false, // 设为透明
        pixelOffset: new Cesium.Cartesian2(0, -25),
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        show: props.showAllLabels && !isCurrent,
      },
    });
    bridgeEntities.push(entity);
  });
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

  // 初始设置地图模式
  updateMapMode(props.mapMode);

  // 设置初始视角到上海
  viewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(121.4737, 31.2304, 20000), // 上海中心城区
    orientation: {
      heading: Cesium.Math.toRadians(0),
      pitch: Cesium.Math.toRadians(-90),
      roll: 0.0
    }
  });

  viewer.scene.globe.enableLighting = false;
  viewer.scene.skyAtmosphere.show = true;
  viewer.scene.globe.depthTestAgainstTerrain = false;

  handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
  handler.setInputAction((movement) => {
    if (props.pickMode) {
      const cartesian = viewer.camera.pickEllipsoid(movement.position, viewer.scene.globe.ellipsoid);
      if (!cartesian) return;
      const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
      const lon = Cesium.Math.toDegrees(cartographic.longitude);
      const lat = Cesium.Math.toDegrees(cartographic.latitude);
      emit("picked", { lon, lat });
    } else {
      // 这里的逻辑可以保留或者扩展为点击 Marker 选择桥梁
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  // 初始渲染
  renderBridges();
});

onBeforeUnmount(() => {
  try {
    if (handler) handler.destroy();
    if (viewer && !viewer.isDestroyed()) viewer.destroy();
  } catch (_e) {
    // ignore
  }
});

function flyToBridge(bridge, height = 1200) {
  if (!viewer || !bridge) return;
  // 优先使用 WGS84 坐标
  let lon = Number(bridge.wgs_lon || bridge.lon);
  let lat = Number(bridge.wgs_lat || bridge.lat);
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return;

  // 兜底纠偏
  if (Math.abs(lon) <= 90 && Math.abs(lat) > 90 && Math.abs(lat) <= 180) {
    [lon, lat] = [lat, lon];
  }
  if (Math.abs(lon) > 180 || Math.abs(lat) > 90) return;

  const position = Cesium.Cartesian3.fromDegrees(lon, lat, 10);

  // 高亮当前选中的标记 (查询点)
  if (markerEntity) viewer.entities.remove(markerEntity);
  markerEntity = viewer.entities.add({
    name: "当前选中",
    position,
    point: {
      pixelSize: 12,
      color: Cesium.Color.CYAN.withAlpha(0.95),
      outlineWidth: 0, // 移除当前选中的描边
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      show: true, // 查询点始终显示，不受全局按钮影响
    },
    label: {
      text: `${bridge.name}\n(${lon.toFixed(5)}, ${lat.toFixed(5)})`,
      font: "bold 14px sans-serif",
      fillColor: Cesium.Color.YELLOW,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 3,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      showBackground: false,
      pixelOffset: new Cesium.Cartesian2(0, -32),
      heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      show: true, // 查询点名称始终显示，不受全局按钮影响
    },
  });

  // 更新所有基础标记的显示状态
  bridgeEntities.forEach((e) => {
    const bridgeId = e.id.split("-")[1];
    // 基础标签：受 showAllLabels 控制，且如果是当前选中的，基础标签隐藏（由 markerEntity 显示）
    e.label.show = props.showAllLabels && String(bridgeId) !== String(bridge.id);
    // 基础点位：受 showAllPoints 控制
    e.point.show = props.showAllPoints;
  });

  viewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(lon, lat, height),
  });
}

defineExpose({
  flyToBridge,
  updateGnnVisualization
});

watch(
  () => props.bridges,
  () => renderBridges(),
  { deep: true }
);

watch(
  () => props.showAllPoints,
  (val) => {
    bridgeEntities.forEach((e) => (e.point.show = val));
  }
);

watch(
  () => props.showAllLabels,
  (val) => {
    bridgeEntities.forEach((e) => {
      const bridgeId = e.id.split("-")[1];
      e.label.show = val && (props.currentBridge ? String(bridgeId) !== String(props.currentBridge.id) : true);
    });
  }
);

watch(
  () => props.mapMode,
  (val) => {
    updateMapMode(val);
  }
);

watch(
  () => props.currentBridge,
  async (bridge) => {
    if (!viewer || !bridge) return;
    flyToBridge(bridge, 1000);
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
