<template>
  <div class="traffic-inference">
    <!-- =====================================================
         面板 1: 流量预测模块（平铺直接显示）
         ===================================================== -->
    <div class="glass-panel flat-panel pred-engine-panel">
      <div class="flat-subtitle pred">
        流量预测模块
        <el-tag size="small" effect="dark" class="menu-tag pred-tag">V-STGRN</el-tag>
      </div>
      <h2 class="gradient-title">交通流实时预测系统</h2>

      <!-- 流量徽标 + 全量底图（上排） -->
      <div class="form-row topo-row topo-row-top">
        <div class="layer-switch-item">
          <el-switch v-model="localShowFlowBadge" size="small" @change="toggleFlowBadge" />
          <span class="layer-switch-label">流量徽标 (推演后)</span>
        </div>
        <div class="layer-switch-item">
          <el-switch v-model="localShowHighway" size="small" :disabled="true" />
          <span class="layer-switch-label">全量底图 (Cesium)</span>
        </div>
      </div>
      <!-- 路网连线（下排） -->
      <div class="form-row topo-row">
        <div class="layer-switch-item">
          <el-switch v-model="localShowLinkMatrix" size="small" @change="toggleLinkMatrix" style="--el-switch-on-color: #38BDF8;" />
          <span class="layer-switch-label">显示路网连线 (link_matrix)</span>
        </div>
      </div>
      <div class="hint" v-if="topologyStats">
        <span class="dot-color" style="background:#00FFAA"></span> 网络节点: {{ topologyStats.num_nodes }} &nbsp;·&nbsp;
        <span class="line-color"></span> 路网连线: {{ topologyStats.num_links }}
      </div>

      <el-divider class="divider" />

      <!-- 时间选择（对齐 HTML: glass-select 深色 + 翡翠绿焦点） -->
      <div class="section-subtitle">选择推演时间</div>
      <div class="time-row">
        <el-select v-model="params.weekday" class="glass-select" placeholder="星期">
          <el-option v-for="w in weekdays" :key="w.value" :label="w.labelFull" :value="w.value" />
        </el-select>
        <el-select v-model="params.hourStr" class="glass-select" placeholder="时刻">
          <el-option v-for="hh in 24" :key="hh-1" :label="String(hh-1).padStart(2,'0') + ':00'" :value="String(hh-1).padStart(2,'0') + ':00'" />
        </el-select>
      </div>

      <!-- 翡翠绿按钮，完全对齐 HTML play-btn -->
      <button
        class="run-pred-btn"
        :disabled="running"
        @click="runInference"
      >
        <span v-if="running" class="spin-dot"></span>
        {{ running ? 'V-STGRN 推演计算中 (~40s) ...' : '▶ 启动 AI 预测引擎' }}
      </button>

      <div class="pred-timeline" v-if="inferenceResult">
        <div class="pred-time-label">预测推演时间: {{ stats.currentTime }}</div>
      </div>
    </div>

    <!-- =====================================================
         面板 2: 元素图例（平铺直接显示）
         ===================================================== -->
    <div class="glass-panel flat-panel legend-panel">
      <div class="flat-subtitle legend">
        元素图例
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background:#00FFAA"></span>
        <span class="legend-label green-key">网络节点:</span>
        <span class="legend-val">桥隧空间静态拓扑点</span>
      </div>
      <div class="legend-item">
        <span class="legend-line"></span>
        <span class="legend-label blue-key">路网连线:</span>
        <span class="legend-val">邻接路网直达拓扑路径</span>
      </div>
      <div class="legend-item legend-congestion">
        <span class="legend-sm-dot" style="background:#EF4444"></span><span class="lg-txt red">拥堵 (RED)</span>
        <span class="legend-sm-dot" style="background:#FACC15"></span><span class="lg-txt yellow">缓行 (CYAN)</span>
        <span class="legend-sm-dot" style="background:#10B981"></span><span class="lg-txt green">畅通 (GREEN)</span>
      </div>
    </div>

    <!-- =====================================================
         面板 4: 推演结果与播放控制（有数据才显示）
         ===================================================== -->
    <div v-if="inferenceResult" class="glass-panel flat-panel result-panel">
      <div class="flat-subtitle result">
        推演结果与播放
        <el-tag size="small" class="result-tag">
          Step {{ stats.current.step }}/{{ stats.current.total }}
        </el-tag>
      </div>
      <!-- 统计卡片 3 列 颜色对齐 -->
      <div class="stat-grid">
        <div class="stat-card red-card">
          <div class="stat-num">{{ stats.current.red }}</div>
          <div class="stat-txt">拥堵 RED (≥1200 辆/h)</div>
        </div>
        <div class="stat-card yellow-card">
          <div class="stat-num">{{ stats.current.orange }}</div>
          <div class="stat-txt">缓行 YELLOW (≥600 辆/h)</div>
        </div>
        <div class="stat-card green-card">
          <div class="stat-num">{{ stats.current.green }}</div>
          <div class="stat-txt">畅通 GREEN (&lt;600 辆/h)</div>
        </div>
      </div>

      <div class="meta-line">基准时刻：{{ inferenceResult.map_data.base_timestamp }}</div>

      <!-- 播放器（扁平化设计，对齐 HTML 翡翠绿循环播放） -->
      <div class="player-bar">
        <button class="flat-step-btn" :disabled="stepIndex <= 0 || playing" @click="prevStep" title="上一步">
          <svg viewBox="0 0 24 24"><path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <button class="flat-play-btn" :class="{ playing }" @click="togglePlay">
          <svg v-if="!playing" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" fill="currentColor"/></svg>
          <svg v-else viewBox="0 0 24 24"><rect x="7" y="5" width="3.4" height="14" rx="1" fill="currentColor"/><rect x="13.6" y="5" width="3.4" height="14" rx="1" fill="currentColor"/></svg>
          <span>{{ playing ? '停止播放' : '循环播放' }}</span>
        </button>
        <button class="flat-step-btn" :disabled="stepIndex >= inferenceResult.map_data.total_steps - 1 || playing" @click="nextStep" title="下一步">
          <svg viewBox="0 0 24 24"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>

      <el-slider
        v-model="stepIndex"
        :min="0"
        :max="inferenceResult.map_data.total_steps - 1"
        :step="1"
        size="small"
        :marks="sliderMarks"
        @change="onSliderChange"
      />

      <div class="btn-row">
        <button class="ghost-btn" @click="resetVisual">↺ 重置视觉</button>
      </div>
    </div>

    <!-- =========================================================
         节点折线图模态框 (完全对齐 link_shanghai-1.py HTML)
         点击 3D 地球上任意桥梁自动弹出此模态框

         🚩 关键修复：用 <Teleport to="body"> 把 Dialog 从 380px 左栏抽离，放到 body 顶层
         → ✅ 不再被侧边栏挤压；✅ 正确全屏显示在地图界面（用户要的效果）
         → ✅ 加 append-to-body（Element Plus 保险）
         ========================================================= -->
    <Teleport to="body">
      <el-dialog
        v-model="chartModal.visible"
        width="min(1200px, 82vw)"
        :close-on-click-modal="true"
        :modal="true"
        class="chart-modal-dialog"
        align-center
        destroy-on-close
        z-index="99999"
        @closed="disposeChart"
        @opened="forceDarkDialog"
      >
        <template #header>
          <div class="chart-modal-header">
            <h2 class="chart-modal-title">
              Real-Time Forecast
            </h2>
            <div class="chart-modal-subtitle">
              <span class="subtitle-line">网络拓扑节点：{{ chartModal.bridgeName }}</span>
              <span class="subtitle-line">节点编号：{{ chartModal.displayIdx }}</span>
            </div>
          </div>
        </template>
        <div ref="echartsDomRef" class="echarts-container"></div>
      </el-dialog>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onBeforeUnmount, reactive, ref, watch } from "vue";
import { ElMessage, ElNotification } from "element-plus";
import * as echarts from "echarts";
import client from "../api/client";


/* --- 折线图模态框 & ECharts 实例 --- */
const chartModal = reactive({
  visible: false,
  bridgeName: "",
  displayIdx: "",
  arrayIdx: -1,
  node0Base: -1,
});
const echartsDomRef = ref(null);
let myChart = null;

function disposeChart() {
  if (myChart) { try { myChart.dispose(); } catch {} myChart = null; }
}

/* 强制将 teleported 弹窗染成深色 —— 直接操作 DOM inline style，无视 Element Plus CSS 变量
   关键：class="chart-modal-dialog" 可能被 Vue 3 inheritAttrs 挂到 overlay 根元素上，
   此时 .chart-modal-dialog 就是 overlay 本身，而 .el-dialog 是它的后代。            */
function forceDarkDialog() {
  const DARK = "#0B1221";
  const containers = document.querySelectorAll(".chart-modal-dialog");

  containers.forEach((container) => {
    /* 1. 定位实际的 .el-dialog 元素 —— 可能是 container 自身，也可能是后代 */
    let dialogEl = container.classList.contains("el-dialog")
      ? container
      : container.querySelector(".el-dialog");
    if (!dialogEl) dialogEl = container; // fallback

    /* 2. dialog 本体 */
    [
      "background", "background-color",
    ].forEach((prop) => {
      dialogEl.style.setProperty(prop, DARK, "important");
    });
    dialogEl.style.setProperty("--el-dialog-bg-color", DARK, "important");
    dialogEl.style.setProperty("--el-bg-color-overlay", DARK, "important");
    dialogEl.style.setProperty("--el-bg-color", DARK, "important");
    dialogEl.style.setProperty("--el-fill-color-blank", DARK, "important");
    dialogEl.style.setProperty("--el-fill-color-light", "rgba(56,189,248,0.05)", "important");
    dialogEl.style.setProperty("--el-color-white", DARK, "important");
    dialogEl.style.setProperty("color", "#fff", "important");
    dialogEl.style.setProperty("border", "1px solid rgba(56, 189, 248, 0.25)", "important");
    dialogEl.style.setProperty("box-shadow", "0 0 30px rgba(56,189,248,0.15), 0 10px 40px rgba(0,0,0,0.7)", "important");

    /* 3a. header — 中间面板配色 (#111827 + 渐变) */
    const HEADER_BG = "#111827";
    const HEADER_GRADIENT = "linear-gradient(90deg, rgba(16, 185, 129, 0.06) 0%, rgba(56, 189, 248, 0.03) 100%)";
    dialogEl.querySelectorAll(".el-dialog__header").forEach((child) => {
      child.style.setProperty("background", HEADER_BG, "important");
      child.style.setProperty("background-image", HEADER_GRADIENT, "important");
      child.style.setProperty("border-bottom", "none", "important");
      child.style.setProperty("color", "#fff", "important");
    });
    /* 3b. body / footer — 深色铺满 */
    dialogEl.querySelectorAll(".el-dialog__body, .el-dialog__footer").forEach((child) => {
      child.style.setProperty("background", DARK, "important");
      child.style.setProperty("background-color", DARK, "important");
      child.style.setProperty("color", "#fff", "important");
      child.style.setProperty("flex", "1", "important");
    });
    // 关闭按钮透明
    dialogEl.querySelectorAll(".el-dialog__headerbtn").forEach((btn) => {
      btn.style.setProperty("background", "transparent", "important");
      btn.style.setProperty("background-color", "transparent", "important");
    });
    // 关闭按钮图标颜色
    dialogEl.querySelectorAll(".el-dialog__headerbtn .el-dialog__close").forEach((icon) => {
      icon.style.setProperty("color", "#94A3B8", "important");
    });

    /* 4. 向上找所有 overlay / wrapper 层，确保无白底 */
    const overlayDialog = dialogEl.closest(".el-overlay-dialog");
    if (overlayDialog) {
      overlayDialog.style.setProperty("background", "transparent", "important");
      overlayDialog.style.setProperty("background-color", "transparent", "important");
    }
    const overlay = dialogEl.closest(".el-overlay");
    if (overlay) {
      overlay.style.setProperty("background-color", "rgba(0, 0, 0, 0.6)", "important");
    }
    // container 本身也强制透明（如果它不是 dialogEl）
    if (container !== dialogEl) {
      container.style.setProperty("background", "transparent", "important");
      container.style.setProperty("background-color", "transparent", "important");
    }
  });
}

/* 每次弹窗打开时（v-model 变 true）多次延迟染色，确保覆盖 Element Plus 动画 */
watch(
  () => chartModal.visible,
  (val) => {
    if (val) {
      // 立即执行一次
      nextTick(forceDarkDialog);
      // 多帧延迟兜底
      [50, 150, 400, 800].forEach((ms) => setTimeout(forceDarkDialog, ms));
    }
  }
);

onBeforeUnmount(() => { stopPlay(); disposeChart(); });

/* 给 App.vue 调用：点击 Cesium 上的桥梁时触发
   新增参数 node0Base → 优先用 0 基 node_id 精确匹配 chart_data 里的 "Node_{node0Base}"（用户要求连线/节点都对齐 CSV 的 0 基）
*/
async function openBridgeChart({ bridge, arrayIndex, node0Base }) {
  if (!inferenceResult.value || !Array.isArray(inferenceResult.value.chart_data)) {
    ElMessage.warning("请先执行 V-STGRN 推演，再点击节点查看折线图");
    return;
  }
  const chartDataLen = inferenceResult.value.chart_data.length;

  /* ✅ 关键修复：优先用 node0Base 定位；如果 chart_data[i].node_id === Node_{node0Base} 就用它；否则 fallback arrayIndex */
  let useIdx = -1;
  const n0bFinite = Number.isFinite(node0Base) && node0Base >= 0;
  if (n0bFinite) {
    const idxByNodeStr = inferenceResult.value.chart_data.findIndex((d) => {
      const nid = String(d.node_id ?? d.node ?? d.index ?? "");
      return nid === `Node_${node0Base}` || nid === String(node0Base) || Number(d.node_0base ?? d.node_idx) === Number(node0Base);
    });
    if (idxByNodeStr >= 0) useIdx = idxByNodeStr;
    else if (node0Base < chartDataLen) useIdx = node0Base;
  }
  if (useIdx < 0 && Number.isFinite(arrayIndex) && arrayIndex >= 0 && arrayIndex < chartDataLen) {
    useIdx = arrayIndex;
  }

  if (useIdx < 0) {
    ElMessage.warning("该节点不在推演的 chart_data 范围内");
    return;
  }
  chartModal.visible = true;
  chartModal.bridgeName = bridge?.name || `节点 ${useIdx + 1}`;
  chartModal.arrayIdx = useIdx;
  chartModal.node0Base = n0bFinite ? Number(node0Base) : -1;
  const disp =
    bridge?.display_idx != null && !Number.isNaN(Number(bridge.display_idx))
      ? Number(bridge.display_idx)
      : n0bFinite
        ? Number(node0Base) + 1
        : useIdx + 1;
  chartModal.displayIdx = String(disp);
  /* 副标题仅展示：网络拓扑节点 + 节点编号（模板中直接渲染） */

  await nextTick();
  if (!echartsDomRef.value) return;
  if (!myChart) myChart = echarts.init(echartsDomRef.value);
  renderBridgeChart(useIdx);
}

/* 完全对齐 link_shanghai HTML openChart() 的 ECharts option 配置 */
function renderBridgeChart(arrayIdx) {
  const dataObj = inferenceResult.value.chart_data[arrayIdx];
  if (!dataObj || !myChart) return;
  const xAxisData = dataObj.x_axis_times || [];
  const pastData = dataObj.series?.history_data || [];
  const futureData = dataObj.series?.forecast_data || [];

  let splitIndex = 0;
  for (let i = 0; i < futureData.length; i++) {
    if (futureData[i] !== null) { splitIndex = i; break; }
  }

  /* 严格对齐 HTML: openChart 里写死的配置 */
  const option = {
    backgroundColor: "rgba(11, 18, 33, 0.95)",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: "#334155", type: "dashed" } },
      backgroundColor: "rgba(11, 18, 33, 0.95)",
      borderColor: "rgba(56, 189, 248, 0.3)",
      textStyle: { color: "#E2E8F0" },
    },
    legend: {
      data: ["Past Data", "Forecast Data"],
      textStyle: { color: "#CBD5E1", fontSize: 13 },
      right: "5%",
      top: "0%",
      icon: "circle",
    },
    grid: { left: "3%", right: "4%", bottom: "5%", containLabel: true },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: xAxisData,
      axisLine: { lineStyle: { color: "#334155" } },
      axisLabel: { color: "#94A3B8", fontSize: 11 },
      splitLine: { show: true, lineStyle: { color: "#1E293B", type: "dashed" } },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: "#94A3B8" },
      splitLine: { lineStyle: { color: "#1E293B", type: "dashed" } },
    },
    series: [
      {
        name: "Past Data",
        type: "line",
        smooth: false,
        symbol: "circle",
        symbolSize: 8,
        itemStyle: { color: "#00F6FF" },
        lineStyle: { color: "#00F6FF", width: 2 },
        data: pastData,
        markLine: {
          symbol: ["none", "none"],
          label: { show: false },
          lineStyle: { color: "#64748B", type: "dashed", width: 2 },
          data: [{ xAxis: splitIndex }],
        },
      },
      {
        name: "Forecast Data",
        type: "line",
        smooth: false,
        symbol: "path://M-5,-5 L5,5 M-5,5 L5,-5",
        symbolSize: 10,
        itemStyle: { color: "#38BDF8" },
        lineStyle: { color: "#38BDF8", width: 2, type: "dashed" },
        data: futureData,
      },
    ],
  };
  myChart.setOption(option, true);
}

defineExpose({ openBridgeChart });

const props = defineProps({
  mapRef: { type: Object, default: null },
});

const emit = defineEmits(["open-deduction-page", "open-chart"]);

const weekdays = [
  { value: 1, label: "周一", labelFull: "星期一" },
  { value: 2, label: "周二", labelFull: "星期二" },
  { value: 3, label: "周三", labelFull: "星期三" },
  { value: 4, label: "周四", labelFull: "星期四" },
  { value: 5, label: "周五", labelFull: "星期五" },
  { value: 6, label: "周六", labelFull: "星期六" },
  { value: 7, label: "周日", labelFull: "星期日" },
];

const params = reactive({
  weekday: 1,       // 对齐实测成功：周一 8:00
  hourStr: "08:00",
});

/* 顶部并列开关的独立状态（模块私有，互不影响） */
const localShowFlowBadge = ref(true);
const localShowHighway = ref(true);
/* 流量徽标：切换仅作用于本模块图层的徽标显示 */
function toggleFlowBadge(v) {
  localShowFlowBadge.value = v;
  const mapRef = props.mapRef;
  if (mapRef && typeof mapRef.setLabelLayer === "function") {
    mapRef.setLabelLayer({ showFlowBadge: v });
  }
}

const topologyStats = ref(null);
/* 开关状态完全由本模块独立持有（模块私有状态），
   不再与父组件或其他模块共享/联动，开/关仅影响本模块控制的图层 */
const localShowTopology = ref(true);
const localShowLinkMatrix = ref(true);
const running = ref(false);
const inferenceResult = ref(null);
const stepIndex = ref(0);
const playing = ref(false);
let playTimer = null;

const sliderMarks = computed(() => {
  if (!inferenceResult.value) return {};
  const data = inferenceResult.value.map_data.data || [];
  const N = inferenceResult.value.map_data.total_steps;
  const mk = {};
  // forecast_time 从 base+30min 开始，只有整点步（HH:00）才显示时间标记
  for (let i = 0; i < N; i++) {
    const t = data[i]?.forecast_time || "";
    const hm = t.split(" ")[1] ? t.split(" ")[1].slice(0, 5) : "";
    if (hm.endsWith(":00")) mk[i] = { label: hm };
  }
  return mk;
});

const stats = computed(() => {
  if (!inferenceResult.value) return { current: { step: 0, total: 0, red: 0, orange: 0, green: 0 } };
  const stepData = inferenceResult.value.map_data.data[stepIndex.value];
  let red = 0, orange = 0, green = 0;
  (stepData?.nodes || []).forEach((n) => {
    const f = parseFloat(n.flow_pred);
    if (f >= 1200) red++;
    else if (f >= 600) orange++;
    else green++;
  });
  return {
    current: {
      step: stepIndex.value + 1,
      total: inferenceResult.value.map_data.total_steps,
      red, orange, green,
      timeLabel: stepData?.forecast_time || "",
    },
    currentTime: `T+${stepIndex.value * 30} 分钟 (${stepData?.forecast_time || ""})`,
  };
});

async function loadTopology() {
  try {
    const { data } = await client.get("/gnn/topology");
    topologyStats.value = data;
    const mapRef = props.mapRef;
    if (mapRef && typeof mapRef.renderTopology === "function") {
      mapRef.renderTopology(data);
      setTimeout(() => mapRef.setTopologyVisible?.(localShowTopology.value), 100);
    }
    console.log("[Topology] 载入完成:", data.num_nodes, "节点,", data.num_links, "连线");
  } catch (e) {
    console.warn("[Topology] 加载失败:", e.message);
  }
}

/* 拓扑连线开关：仅本模块生效，不回写父组件、不联动其他模块 */
function toggleTopology(v) {
  localShowTopology.value = v;
  const mapRef = props.mapRef;
  if (mapRef) mapRef.setTopologyVisible?.(v);
}

/* 路网连线开关：仅本模块生效，不回写父组件、不联动其他模块 */
function toggleLinkMatrix(v) {
  localShowLinkMatrix.value = v;
  const mapRef = props.mapRef;
  if (mapRef) mapRef.setLinkMatrixVisible?.(v);
}

function hourFromStr() {
  if (!params.hourStr) return 8;
  return parseInt(params.hourStr.split(":")[0], 10) || 8;
}

async function runInference() {
  if (running.value) return;
  stopPlay();
  running.value = true;
  const weekLabel = weekdays.find((w) => w.value === params.weekday)?.label || "";
  const hh = hourFromStr();
  try {
    ElNotification({
      title: "AI 开始推演",
      message: `时段: ${weekLabel} ${String(hh).padStart(2, "0")}:00，模型: V-STGRN，预计用时 30-60 秒`,
      type: "info",
      duration: 6000,
      position: "bottom-right",
    });
    const t0 = Date.now();
    // 单独给这个长耗时接口设置 10 分钟超时，不受全局 2 分钟限制
    const { data } = await client.post("/gnn/inference_real", {
      weekday: params.weekday,
      hour: hh,
    }, { timeout: 600 * 1000 });
    const dt = ((Date.now() - t0) / 1000).toFixed(1);
    if (!data.map_data) {
      ElMessage.error(data.error || "推演无数据返回");
      return;
    }
    inferenceResult.value = data;
    stepIndex.value = 0;
    ElMessage.success(`推演完成！耗时 ${dt}s，共 ${data.map_data.total_steps} 个时间步`);
    applyStep(0);
  } catch (e) {
    const msg = e.response?.data?.error || e.response?.data?.message || e.message || "推演失败";
    ElMessage.error(msg);
    console.error(e);
  } finally {
    running.value = false;
  }
}

function applyStep(idx) {
  const mapRef = props.mapRef;
  if (!mapRef || !inferenceResult.value) return;
  const stepData = inferenceResult.value.map_data.data[idx];
  if (!stepData) return;
  if (typeof mapRef.updateInferenceVisualization === "function") {
    mapRef.updateInferenceVisualization({
      stepData,
      stepIndex: idx,
      totalSteps: inferenceResult.value.map_data.total_steps,
    });
  } else if (typeof mapRef.updateGnnVisualization === "function") {
    mapRef.updateGnnVisualization({
      stepData, stepIndex: idx, totalSteps: inferenceResult.value.map_data.total_steps,
    });
  }
}

function onSliderChange(v) {
  applyStep(v);
}

function prevStep() { if (stepIndex.value > 0) { stepIndex.value--; applyStep(stepIndex.value); } }
function nextStep() {
  if (!inferenceResult.value) return;
  if (stepIndex.value < inferenceResult.value.map_data.total_steps - 1) {
    stepIndex.value++; applyStep(stepIndex.value);
  }
}

function togglePlay() { playing.value ? stopPlay() : startPlay(); }
function startPlay() {
  playing.value = true;
  playTimer = setInterval(() => {
    if (!inferenceResult.value) return stopPlay();
    const total = inferenceResult.value.map_data.total_steps;
    // 循环播放：到末尾后回到第 0 步继续，直到用户点击停止播放
    stepIndex.value = (stepIndex.value + 1) % total;
    applyStep(stepIndex.value);
  }, 1500);
}
function stopPlay() {
  playing.value = false;
  if (playTimer) { clearInterval(playTimer); playTimer = null; }
}

function resetVisual() {
  const mapRef = props.mapRef;
  if (mapRef) mapRef.resetVisualization?.();
  ElMessage.info("已重置 3D 地球视觉");
}

watch(() => props.mapRef, (ref) => {
  if (ref && topologyStats.value) {
    setTimeout(() => {
      ref.renderTopology?.(topologyStats.value);
      ref.setTopologyVisible?.(localShowTopology.value);
      ref.setLinkMatrixVisible?.(localShowLinkMatrix.value);
    }, 200);
  }
});

onMounted(() => {
  setTimeout(() => loadTopology(), 1500);
});
onBeforeUnmount(() => stopPlay());
</script>

<style scoped>
/* =========================================================
   完全对齐 link_shanghai-1.py HTML 玻璃面板样式
   ========================================================= */
.traffic-inference {
  padding: 4px 2px 12px 2px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* --- 玻璃容器: 对齐 HTML rgba(30,41,59,0.85) + blur(8px) + 翡翠绿边框 --- */
.glass-panel {
  background: rgba(11, 18, 33, 0.92);
  border: 1px solid rgba(56, 189, 248, 0.25);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  overflow: hidden;
}

/* --- 玻璃容器基础 (flat-panel，直接显示无折叠) --- */
.flat-panel {
  padding: 14px;
  overflow: hidden;
}

/* --- 面板小标题（替代原来的 collapsible-header，可点击色（非折叠）*/
.flat-subtitle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0 10px 0;
  margin-bottom: 8px;
  border-bottom: 1px solid rgba(100, 116, 139, 0.22);
  background: linear-gradient(90deg,
    rgba(16, 185, 129, 0.06) 0%,
    rgba(56, 189, 248, 0.03) 100%);
  padding: 9px 12px;
  margin: -14px -14px 12px -14px;
}
.flat-subtitle.pred { border-left: 3px solid #10B981; }
.flat-subtitle.layer { border-left: 3px solid #38BDF8; }
.flat-subtitle.legend { border-left: 3px solid #A78BFA; }
.flat-subtitle.result { border-left: 3px solid #38BDF8; }
.flat-subtitle :deep(.menu-title-text) {
  font-size: 14px; font-weight: 700; color: #E2E8F0;
  flex: 1; letter-spacing: 0.5px;
}
.flat-subtitle {
  font-size: 14px;
  font-weight: 700;
  color: #E2E8F0;
  flex: 1;
  letter-spacing: 0.5px;
}

/* --- 标题渐变: linear-gradient(90deg, #00FFAA 薄荷绿, #38BDF8 星空蓝) --- */
.gradient-title {
  margin: 0 0 12px 0;
  font-size: 16px;
  font-weight: 900;
  letter-spacing: 1px;
  background: linear-gradient(90deg, #00FFAA 0%, #38BDF8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-align: center;
  display: block;
}

.panel-subheader {
  color: #94A3B8;
  font-size: 12px;
  margin-bottom: 10px;
  letter-spacing: 0.5px;
  font-weight: 500;
}

/* --- 拓扑开关行 --- */
.topo-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.topo-row-top {
  margin-bottom: 2px;
}
.layer-switch-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.layer-switch-label {
  font-size: 11px;
  color: #cbd5e1;
  white-space: nowrap;
}
.hint {
  font-size: 11px;
  color: #94a3b8;
  padding: 6px 0 0 0;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.hint .dot-color {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  border: 1.5px solid #fff;
}
.hint .line-color {
  display: inline-block;
  width: 18px; height: 3px;
  background: #38BDF8;
  border-radius: 2px;
}

.divider {
  margin: 12px 0;
  border-color: rgba(148,163,184,0.15);
}

/* --- 时间选择 --- */
.section-subtitle {
  font-size: 12px;
  font-weight: 600;
  color: #10B981;
  padding-left: 8px;
  border-left: 2px solid #10B981;
  margin: 2px 0 10px 0;
  letter-spacing: 0.5px;
}
.time-row {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}
.glass-select {
  flex: 1;
}
:deep(.glass-select .el-select__wrapper) {
  background: rgba(15, 23, 42, 0.85);
  color: #E2E8F0;
  border: 1px solid rgba(56, 189, 248, 0.4);
  border-radius: 4px;
  box-shadow: none;
  transition: 0.3s;
}
:deep(.glass-select .el-select__wrapper:hover),
:deep(.glass-select.is-focused .el-select__wrapper) {
  border-color: #00FFAA;
  box-shadow: 0 0 5px rgba(0, 255, 170, 0.45);
}

/* --- 翡翠绿大按钮: 对齐 HTML play-btn (#10B981) --- */
.run-pred-btn {
  width: 100%;
  padding: 11px 12px;
  background: rgba(16, 185, 129, 0.15);
  color: #10B981;
  border: 1px solid rgba(16, 185, 129, 0.5);
  border-radius: 4px;
  font-size: 14px;
  font-weight: bold;
  cursor: pointer;
  transition: 0.25s all;
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.2);
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.run-pred-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
  border-color: rgba(16, 185, 129, 0.8);
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
}
.run-pred-btn:disabled {
  background: rgba(148, 163, 184, 0.08);
  border-color: rgba(148, 163, 184, 0.25);
  color: rgba(148, 163, 184, 0.5);
  cursor: not-allowed;
}
.spin-dot {
  width: 12px; height: 12px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.45);
  border-top-color: #fff;
  animation: spin-dot 0.8s linear infinite;
}
@keyframes spin-dot { to { transform: rotate(360deg); } }

.pred-timeline {
  margin-top: 14px;
  text-align: center;
}
.pred-time-label {
  font-size: 13px;
  color: #fff;
  font-weight: bold;
  margin-bottom: 8px;
}

/* --- 元素图例 --- */
.legend-item {
  display: flex;
  align-items: center;
  font-size: 13px;
  margin-bottom: 8px;
  gap: 8px;
}
.legend-dot {
  width: 12px; height: 12px;
  border-radius: 50%;
  border: 2px solid #fff;
  flex-shrink: 0;
}
.legend-sm-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.legend-line {
  width: 24px; height: 3px;
  background: #38BDF8;
  border-radius: 1.5px;
  flex-shrink: 0;
}
.legend-label { font-weight: bold; margin-right: 4px; white-space: nowrap; }
.legend-label.green-key { color: #00FFAA; }
.legend-label.blue-key  { color: #38BDF8; }
.legend-val { color: #E2E8F0; font-size: 12px; }
.legend-congestion {
  flex-wrap: wrap;
  gap: 6px 4px;
}
.lg-txt { font-size: 12px; font-weight: bold; margin-right: 14px;}
.lg-txt.red { color: #EF4444; }
.lg-txt.yellow { color: #FACC15; }
.lg-txt.green { color: #10B981; }

/* --- 推演结果 --- */
.result-tag {
  margin-left: 10px;
  background: rgba(56, 189, 248, 0.14) !important;
  border: 1px solid rgba(56, 189, 248, 0.38) !important;
  color: #7DD3FC !important;
  border-radius: 6px;
  font-weight: 700;
  padding: 0 7px;
  height: 20px;
  line-height: 18px;
}

/* 菜单标签 (TrafficInference 内的 V-STGRN 标签) */
.menu-tag {
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  color: #ECFDF5;
  background: linear-gradient(90deg, #10B981, #059669);
  border: none;
}
.pred-tag {
  background: linear-gradient(90deg, #10B981, #059669);
}
.menu-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(56, 189, 248, 0.15);
  color: #38BDF8;
  border: 1px solid rgba(56, 189, 248, 0.35);
  font-weight: 700;
  letter-spacing: 0.5px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  margin: 12px 0 12px 0;
}
.stat-card {
  text-align: center;
  padding: 10px 6px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.05);
  background: rgba(15,23,42,0.55);
}
.stat-card.red-card    { border-top: 3px solid #EF4444; }
.stat-card.yellow-card { border-top: 3px solid #FACC15; }
.stat-card.green-card  { border-top: 3px solid #10B981; }
.stat-num {
  font-size: 20px;
  font-weight: 900;
  color: #e2e8f0;
  line-height: 1.1;
}
.stat-card.red-card    .stat-num { color: #fca5a5; }
.stat-card.yellow-card .stat-num { color: #fde047; }
.stat-card.green-card  .stat-num { color: #6ee7b7; }
.stat-txt {
  font-size: 10px;
  color: #94a3b8;
  line-height: 1.35;
  margin-top: 4px;
}
.meta-line {
  font-size: 11px;
  color: #94a3b8;
  padding: 2px 0;
}
.player-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 12px 0 10px 0;
}
.flat-step-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.35);
  color: #7DD3FC;
  cursor: pointer;
  transition: 0.2s;
}
.flat-step-btn svg { width: 18px; height: 18px; }
.flat-step-btn:hover:not(:disabled) {
  background: rgba(56, 189, 248, 0.2);
  border-color: rgba(56, 189, 248, 0.6);
  color: #BAE6FD;
}
.flat-step-btn:disabled {
  opacity: 0.3;
  border-color: rgba(148, 163, 184, 0.2);
  color: rgba(148, 163, 184, 0.3);
  cursor: not-allowed;
}
.flat-play-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 20px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.5);
  color: #10B981;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: 0.25s;
  box-shadow: 0 2px 10px rgba(16, 185, 129, 0.2);
}
.flat-play-btn svg { width: 18px; height: 18px; }
.flat-play-btn:hover {
  background: rgba(16, 185, 129, 0.25);
  border-color: rgba(16, 185, 129, 0.8);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(16, 185, 129, 0.35);
}
.flat-play-btn.playing {
  background: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.5);
  color: #EF4444;
  box-shadow: 0 2px 10px rgba(239, 68, 68, 0.2);
}
.flat-play-btn.playing:hover {
  background: rgba(239, 68, 68, 0.25);
  border-color: rgba(239, 68, 68, 0.8);
  box-shadow: 0 4px 16px rgba(239, 68, 68, 0.35);
}
.btn-row {
  margin-top: 32px;
  display: flex;
  gap: 8px;
}
.ghost-btn {
  flex: 1;
  padding: 8px 10px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.35);
  color: #7DD3FC;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: 0.2s;
}
.ghost-btn:hover {
  background: rgba(56, 189, 248, 0.18);
  border-color: rgba(56, 189, 248, 0.5);
}

/* --- 折线图模态框: 完全对齐 HTML chart-modal --- */
:deep(.chart-modal-dialog.el-dialog) {
  background: #0B1221;
  border-radius: 12px;
  padding: 24px 30px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.7);
  color: #fff;
  border: 1px solid rgba(56, 189, 248, 0.25);
}
:deep(.chart-modal-dialog .el-dialog__header) { padding: 0 0 18px 0; margin-right: 0; }
:deep(.chart-modal-dialog .el-dialog__headerbtn .el-dialog__close) {
  color: #64748B; font-size: 28px; font-weight: 200;
}
:deep(.chart-modal-dialog .el-dialog__headerbtn .el-dialog__close:hover) { color: #fff; }
:deep(.chart-modal-dialog .el-dialog__body) { padding: 0; margin-top: 0; }
.chart-modal-header { text-align: center; }
.chart-modal-title {
  color: #FFFFFF;
  margin: 0;
  letter-spacing: 1px;
  font-weight: 500;
  font-size: 20px;
}
.chart-modal-subtitle {
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: center;
  gap: 24px;
  margin-top: 8px;
}
.chart-modal-subtitle .subtitle-line {
  color: #94A3B8;
  font-size: 13px;
  letter-spacing: 0.5px;
  line-height: 1.6;
}
.echarts-container {
  width: 100%;
  height: 450px;
  background: #0B1221;
  border-radius: 8px;
}
</style>

<!-- 全局样式：修复 Teleport 到 body 的弹窗白色边框/背景问题 -->
<style>
/* 覆盖 Element Plus CSS 变量 —— 从根源消除白色背景 */
.chart-modal-dialog {
  --el-dialog-bg-color: #0B1221 !important;
  --el-bg-color: #0B1221 !important;
  --el-bg-color-overlay: #0B1221 !important;
  --el-fill-color-blank: #0B1221 !important;
  --el-fill-color-light: rgba(56, 189, 248, 0.05) !important;
  --el-color-white: #0B1221 !important;
  --el-text-color-primary: #fff !important;
  --el-text-color-regular: #CBD5E1 !important;
  --el-border-color: rgba(56, 189, 248, 0.15) !important;
}

/* 对话框本身 */
body .el-overlay .chart-modal-dialog.el-dialog,
body .chart-modal-dialog.el-dialog,
.chart-modal-dialog.el-dialog {
  background: #0B1221 !important;
  background-color: #0B1221 !important;
  border: 1px solid rgba(56, 189, 248, 0.25) !important;
  box-shadow: 0 0 30px rgba(56, 189, 248, 0.15), 0 10px 40px rgba(0,0,0,0.7) !important;
  border-radius: 12px !important;
  overflow: hidden;
  color: #fff !important;
}

/* 标题区域 — 匹配中间面板配色 */
body .chart-modal-dialog .el-dialog__header,
.chart-modal-dialog .el-dialog__header {
  background: #111827 !important;
  background-image: linear-gradient(90deg, rgba(16, 185, 129, 0.06) 0%, rgba(56, 189, 248, 0.03) 100%) !important;
  border-bottom: none !important;
  padding: 24px 30px 18px 30px !important;
  margin-right: 0 !important;
}

/* 内容区域 */
body .chart-modal-dialog .el-dialog__body,
.chart-modal-dialog .el-dialog__body {
  background: #0B1221 !important;
  background-color: #0B1221 !important;
  padding: 0 30px 24px 30px !important;
  flex: 1 !important;
}

/* 底部 */
body .chart-modal-dialog .el-dialog__footer,
.chart-modal-dialog .el-dialog__footer {
  background: #0B1221 !important;
  background-color: #0B1221 !important;
  border-top: none !important;
}

/* 关闭按钮 */
body .chart-modal-dialog .el-dialog__headerbtn,
.chart-modal-dialog .el-dialog__headerbtn {
  background: transparent !important;
  background-color: transparent !important;
}

/* ====== 关键：当 chart-modal-dialog 是 overlay 根元素时，.el-dialog 是后代 ====== */
body .chart-modal-dialog .el-dialog,
.chart-modal-dialog .el-dialog {
  background: #0B1221 !important;
  background-color: #0B1221 !important;
  border: 1px solid rgba(56, 189, 248, 0.25) !important;
  box-shadow: 0 0 30px rgba(56, 189, 248, 0.15), 0 10px 40px rgba(0,0,0,0.7) !important;
  border-radius: 12px !important;
  overflow: hidden;
  color: #fff !important;
}

/* 遮罩层 */
body .chart-modal-dialog.el-overlay,
body .el-overlay:has(.chart-modal-dialog),
.chart-modal-dialog.el-overlay,
.el-overlay:has(.chart-modal-dialog) {
  background-color: rgba(0, 0, 0, 0.6) !important;
}

/* 遮罩内层 wrapper */
body .chart-modal-dialog .el-overlay-dialog,
.chart-modal-dialog .el-overlay-dialog {
  background: transparent !important;
  background-color: transparent !important;
}

body .chart-modal-dialog .el-dialog__wrapper,
.chart-modal-dialog .el-dialog__wrapper {
  background: transparent !important;
  background-color: transparent !important;
}

/* 所有 el-dialog 内部元素都强制深色 */
body .chart-modal-dialog .el-dialog .el-dialog__header,
.chart-modal-dialog .el-dialog .el-dialog__header {
  background: #111827 !important;
  background-image: linear-gradient(90deg, rgba(16, 185, 129, 0.06) 0%, rgba(56, 189, 248, 0.03) 100%) !important;
  border-bottom: none !important;
  color: #fff !important;
}
body .chart-modal-dialog .el-dialog .el-dialog__body,
body .chart-modal-dialog .el-dialog .el-dialog__footer,
.chart-modal-dialog .el-dialog .el-dialog__body,
.chart-modal-dialog .el-dialog .el-dialog__footer {
  background: #0B1221 !important;
  background-color: #0B1221 !important;
  color: #fff !important;
  flex: 1 !important;
}

body .chart-modal-dialog .el-dialog .el-dialog__headerbtn,
.chart-modal-dialog .el-dialog .el-dialog__headerbtn {
  background: transparent !important;
  background-color: transparent !important;
}

.toggle-switch.on span.dot { transform: translateX(20px); }
.toggle-switch.link-switch.on { background: rgba(245, 158, 11, 0.25); border-color: #F59E0B; }
.toggle-switch.link-switch.on span.dot { background: #F59E0B; box-shadow: 0 0 8px rgba(245, 158, 11, 0.8); }
</style>
