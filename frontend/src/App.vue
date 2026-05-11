<template>
  <div class="page">
    <!-- 登录遮罩层 -->
    <div v-if="!auth.token" class="login-overlay">
      <div class="login-card">
        <div class="login-header">
          <div class="logo">SH</div>
          <div class="titles">
            <div class="title">上海市桥隧群数字孪生平台</div>
            <div class="subtitle">请登录后继续操作</div>
          </div>
        </div>
        <div class="login-body">
          <el-form label-position="top">
            <el-form-item label="用户名">
              <el-input v-model="loginForm.username" placeholder="请输入用户名" prefix-icon="User" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入密码"
                show-password
                prefix-icon="Lock"
                @keyup.enter="handleLogin"
              />
            </el-form-item>
            <el-button type="primary" class="login-btn" @click="handleLogin">进入平台</el-button>
          </el-form>
        </div>
      </div>
    </div>

    <!-- 主界面内容 -->
    <template v-else>
      <header class="topbar">
        <div class="brand">
          <div class="logo">SH</div>
          <div class="titles">
            <div class="title">上海市桥隧群数字孪生平台</div>
            <div class="subtitle">群桥展示 · 查询 · 管理</div>
          </div>
        </div>
        <div class="top-actions">
          <el-radio-group v-model="viewMode" size="small" class="view-switch" style="margin-right: 18px;">
            <el-radio-button value="map">
              <el-icon><Location /></el-icon>
              <span>地图视图</span>
            </el-radio-button>
            <el-radio-button value="linkmap">
              <el-icon><Connection /></el-icon>
              <span>拓扑地图</span>
            </el-radio-button>
           
          </el-radio-group>
          <el-tag type="success" effect="dark">已登录：{{ auth.user?.username }}</el-tag>
          <el-button link class="logout-link" @click="auth.logout()">退出登录</el-button>
        </div>
      </header>

 
      <ShanghaiLinkMap
        v-if="viewMode === 'linkmap'"
        @back="viewMode = 'map'"
      />

      <el-container v-else class="layout">
        <el-aside :width="sidebarWidth + 'px'" class="panel">
          <div class="sidebar-wrap">

            <!-- =========================================================
                 一级菜单 1:  桥梁选择列表（可折叠）
                 ========================================================= -->
            <div class="glass-panel collapsible-panel">
              <div class="collapsible-header" @click="togglePanel('bridgeList')">
                <span class="menu-chevron" :class="{ open: collapse.bridgeList }"></span>
                <span class="menu-title">桥梁选择列表</span>
                <span class="menu-badge">{{ bridges.length }}</span>
              </div>
              <div class="collapsible-body" v-show="collapse.bridgeList">
                <!--  可搜索下拉选择器（点击才展开所有桥梁，替代 420px 常驻表格） -->
                <div class="bridge-picker-row">
                  <el-select
                    v-model="bridgePickerId"
                    filterable
                    remote
                    clearable
                    reserve-keyword
                    placeholder="搜索桥名/编码 → 点击展开全部桥梁"
                    :remote-method="bridgeRemoteSearch"
                    :loading="bridgePickerLoading"
                    size="default"
                    style="width: 100%;"
                    @change="onBridgePickerChange"
                    class="bridge-picker"
                    popper-class="bridge-picker-popper"
                  >
                    <el-option
                      v-for="(b, idx) in bridgePickerOptions"
                      :key="b.id"
                      :label="`#${b._displayIdx} ${b.name} · ${b.district || '-'}`"
                      :value="b.id"
                    >
                      <div class="bridge-option">
                        <span class="b-code">#{{ b._displayIdx }}</span>
                        <span class="b-name">{{ b.name }}</span>
                        <span class="b-dist">{{ b.district }}</span>
                      </div>
                    </el-option>
                  </el-select>
                </div>

                <!-- 搜索框（联想建议） + 查询按钮 -->
                <el-space wrap style="margin-top: 10px;">
                  <el-autocomplete
                    v-model="searchKeyword"
                    :fetch-suggestions="searchQuerySuggestions"
                    placeholder="搜索序号/桥名"
                    style="width: 190px;"
                    clearable
                    :trigger-on-focus="false"
                    @select="onSearchSuggestionSelect"
                    @keyup.enter="handleSearch"
                    popper-class="search-suggest-popper"
                  >
                    <template #default="{ item }">
                      <div class="search-suggest-item">
                        <span class="b-code">#{{ item._displayIdx }}</span>
                        <span class="b-name">{{ item.name }}</span>
                        <span class="b-dist">{{ item.district }}</span>
                      </div>
                    </template>
                  </el-autocomplete>
                  <el-button type="primary" size="small" @click="handleSearch" :loading="flyingToBridge">
                    {{ flyingToBridge ? '跳转中...' : '查询' }}
                  </el-button>
                </el-space>

                <!-- 搜索结果面板（多结果时展示） -->
                <transition name="slide-down">
                  <div v-if="searchResults.length > 0" class="search-results-panel">
                    <div class="search-results-header">
                      <span>找到 {{ searchResults.length }} 座匹配桥梁</span>
                      <el-button link type="primary" size="small" @click="searchResults = []">收起</el-button>
                    </div> 
                    <div
                      v-for="r in searchResults"
                      :key="r.id"
                      class="search-results-item"
                      :class="{ active: currentBridge?.id === r.id }"
                      @click="onSearchResultClick(r)"
                    >
                      <span class="b-code">#{{ r._displayIdx }}</span>
                      <span class="b-name">{{ r.name }}</span>
                      <span class="b-dist">{{ r.district }}</span>
                    </div>
                  </div>
                </transition>

                <!-- 点显示 + 名显示 + 节点序号（三个 switch 同一行显示） -->
                <div class="switch-row">
                  <div class="switch-item">
                    <el-switch
                      v-model="showAllPoints"
                      inline-prompt
                      active-text="节点显示"
                      inactive-text="节点隐藏"
                    />
                  </div>
                  <div class="switch-item">
                    <el-switch
                      v-model="showNodeIdx"
                      inline-prompt
                      active-text="序号显示"
                      inactive-text="序号隐藏"
                    />
                  </div>
                  <div class="switch-item">
                    <el-switch
                      v-model="showAllLabels"
                      inline-prompt
                      active-text="名称显示"
                      inactive-text="名称隐藏"
                    />
                  </div>
                </div>

                <!-- 单独唤起折线图弹窗（列表选择默认仅定位） -->
                <el-button
                  type="success"
                  size="small"
                  plain
                  :disabled="!currentBridge"
                  @click="viewBridgeChart"
                  style="width: 100%; margin-top: 8px;"
                >
                  查看折线图
                </el-button>
              </div>
            </div>
            <!-- =========================================================
                 一级菜单 2: 上海桥隧蔓延预测（Node版）
                 ========================================================= -->
            <div class="glass-panel collapsible-panel">
              <div class="collapsible-header" @click="togglePanel('gnnOld')">
                <span class="menu-chevron" :class="{ open: collapse.gnnOld }"></span>
                <span class="menu-title">上海桥隧蔓延预测</span>
                <span class="menu-tag" style="background: linear-gradient(90deg, #3B82F6, #60A5FA);">Node.js</span>
              </div>
              <div class="collapsible-body" v-show="collapse.gnnOld">
                <div style="padding: 2px;">
                  
                  <!-- 1. 严格并列的两列参数输入控件 -->
                  <div style="display: flex; gap: 10px; margin-bottom: 12px;">
                    <!-- 起始节点输入框（1 起始） -->
                    <div style="flex: 1; min-width: 0;">
                      <div style="font-size: 12px; color: #94A3B8; margin-bottom: 5px;">起始节点 (node)</div>
                      <el-input-number 
                        v-model="spreadParams.node" 
                        :min="1" 
                        :max="Math.max(bridges.length, 1)" 
                        controls-position="right"
                        size="small" 
                        class="dark-input-number"
                        style="width: 100%;"
                        placeholder="1 ~ N"
                      />
                    </div>
                    <!-- 事件类型选择器 (1, 2, 3) -->
                    <div style="flex: 1; min-width: 0;">
                      <div style="font-size: 12px; color: #94A3B8; margin-bottom: 5px;">事件类型 (typ)</div>
                      <el-select 
                        v-model="spreadParams.typ" 
                        size="small" 
                        class="dark-select"
                        style="width: 100%;">
                        <el-option label="类型 1" :value="1" />
                        <el-option label="类型 2" :value="2" />
                        <el-option label="类型 3" :value="3" />
                      </el-select>
                    </div>
                  </div>

                <!-- 2. 按钮组：启动预测 & 恢复初始 -->
                  <div style="display: flex; gap: 10px;">
                    <el-button 
                      type="primary"
                      @click="runShanghaiSpread" 
                      :loading="isSpreadLoading"
                      style="flex: 2; height: 36px;">
                      {{ isSpreadLoading ? '推演中...' : '启动循环预测' }}
                    </el-button>
                    
                    <el-button 
                      plain
                      @click="resetSpread" 
                      style="flex: 1; height: 36px; background: rgba(148, 163, 184, 0.1); border-color: rgba(148, 163, 184, 0.4); color: #E2E8F0;">
                      恢复初始
                    </el-button>
                  </div>
                  <!-- 3. 推演完成提示框 -->
                  <div v-if="spreadResult" style="margin-top: 12px; font-size: 12px; color: #10B981; background: rgba(16, 185, 129, 0.1); padding: 8px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.3); text-align: center;">
                    推演完成！已成功获取节点 JSON 数据
                  </div>

                </div>
              </div>
            </div>

            <!-- =========================================================
                 一级菜单 3: V-STGRN 流量预测（新版）（可折叠）
                 ========================================================= -->
            <div class="glass-panel collapsible-panel">
              <div class="collapsible-header" @click="togglePanel('gnnNew')">
                <span class="menu-chevron" :class="{ open: collapse.gnnNew }"></span>
                <span class="menu-title">V-STGRN 流量预测</span>
                <span class="menu-tag pred-tag">V-STGRN</span>
              </div>
              <div class="collapsible-body" v-show="collapse.gnnNew">
                <TrafficInference
                  ref="trafficInfRef"
                  :map-ref="cesiumRef"
                  @open-deduction-page="viewMode = 'deduction'"
                />
              </div>
            </div>

          </div>
          <div class="sidebar-resizer" @mousedown="startResize"></div>
        </el-aside>

        <el-main class="map-main">
          <div id="bridge-detail-section" class="map-wrap">
            <CesiumMap
              ref="cesiumRef"
              :current-bridge="currentBridge"
              :bridges="bridges"
              :show-all-points="showAllPoints"
              :show-all-labels="showAllLabels"
              :show-node-idx="showNodeIdx"
              :map-mode="mapMode"
              :model-url="modelUrl"
              @bridge-click-with-index="handleBridgeClickWithIndex"
            />

            <div class="hud">
            <div class="hud-title">地图视图</div>
            <div class="hud-line">
              <span class="k">地图模式</span>
              <el-select v-model="mapMode" size="small" style="width: 120px;">
                <el-option label="幻彩地图" value="voyager" />
                <el-option label="浅色底图" value="light" />
                <el-option label="极夜黑" value="dark" />
                <el-option label="标准街道" value="street" />
                <el-option label="卫星影像" value="satellite" />
              </el-select>
            </div>
            <div class="hud-line">
              <span class="k">当前桥梁</span>
              <span class="v">{{ currentBridge?.name || "未选择" }}</span>
            </div>
              <div class="hud-line">
                <span class="k">模型</span>
                <span class="v">{{ modelUrl ? "已绑定（如存在将加载）" : "未绑定" }}</span>
              </div>
            </div>
          </div>
        </el-main>
      </el-container>
    </template>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import client from "./api/client";
import { useAuthStore } from "./stores/auth";
import CesiumMap from "./components/CesiumMap.vue";
import TrafficInference from "./components/TrafficInference.vue";
import ShanghaiLinkMap from "./components/ShanghaiLinkMap.vue";
import { Location, Connection } from "@element-plus/icons-vue";
import axios from "axios";
const auth = useAuthStore();
const viewMode = ref('map');
const loginForm = reactive({ username: "admin", password: "admin123" });
const query = reactive({ keyword: "", page: 1, pageSize: 500 });
const searchKeyword = ref("");
const bridges = ref([]);
const currentBridge = ref(null);
const modelUrl = ref("");
const cesiumRef = ref(null);
const trafficInfRef = ref(null);
const showAllPoints = ref(true);
const showAllLabels = ref(true);
const showNodeIdx = ref(true);   // 节点序号显示（CesiumMap 标签中的序号部分）
const sidebarWidth = ref(380);
const isResizingSidebar = ref(false);

function startResize(e) {
  isResizingSidebar.value = true;
  const startX = e.clientX;
  const startWidth = sidebarWidth.value;
  const onMove = (ev) => {
    const delta = ev.clientX - startX;
    sidebarWidth.value = Math.min(620, Math.max(280, startWidth + delta));
  };
  const onUp = () => {
    isResizingSidebar.value = false;
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
  };
  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onUp);
}
const mapMode = ref("voyager");

const selectedBridge = ref(null);   // 当前选中桥梁（同步 Cesium 高亮）
const flyingToBridge = ref(false);  // 跳转加载状态
const searchResults = ref([]);      // 搜索多结果列表

/* --- 上海交通蔓延预测参数与运行逻辑 --- */
const isSpreadLoading = ref(false);
const spreadResult = ref(null);
let spreadTimer = null;
// 1. 定义两个参数的默认值（UI 界面从 1 开始展示）
const spreadParams = reactive({
  node: 1,
  typ: 2
});

// 2. 当在地图或列表选桥时：取底层的 0 编号并 +1 同步到输入框
watch(currentBridge, (bridge) => {
  if (bridge) {
    const raw0 = bridge.node_0base != null ? Number(bridge.node_0base) : 0;
    spreadParams.node = raw0 + 1; // 转换为 1 起始显示
  }
});

async function runShanghaiSpread() {
  isSpreadLoading.value = true;
  spreadResult.value = null;

  if (spreadTimer) clearInterval(spreadTimer);
  cesiumRef.value?.resetSpreadVisualization?.();

  try {
    // 将输入的 1 起始编号减 1，还原为 Python 底层需要的 0 起始编号
    const targetNode0Base = Math.max(0, Number(spreadParams.node) - 1);
    const targetNode = String(targetNode0Base);
    const eventType = Number(spreadParams.typ);

    console.log(`🚀 启动模型推演 - 界面展示: #${spreadParams.node} -> 传给Python: node = "${targetNode}", typ = ${eventType}`);

    const response = await client.post('/python/start-shanghai', {
      node: targetNode,
      typ: eventType
    });

    const result = response.data;
    spreadResult.value = result;
    ElMessage.success("蔓延模拟完成，开始循环推演地图！"); // 提示语更新

    let sequenceList = [];
    if (Array.isArray(result)) {
      sequenceList = result;
    } else {
      const arrayKey = Object.keys(result).find(k => Array.isArray(result[k]));
      sequenceList = arrayKey ? result[arrayKey] : [];
    }

    if (!sequenceList || sequenceList.length === 0) {
      ElMessage.warning("未解析到有效的蔓延序列数据");
      return;
    }

    let currentIndex = 0;
    const playSpeed = 60;

    spreadTimer = setInterval(() => {
      // 循环播放核心逻辑
      if (currentIndex >= sequenceList.length) {
        currentIndex = 0; // 重置索引
        cesiumRef.value?.resetSpreadVisualization?.(); // 清理地图上的高亮红点
        return; // 直接 return，制造一帧的视觉停顿，然后进入下一次循环
      }

      const item = sequenceList[currentIndex];
      if (item && item.node !== undefined) {
        // Python 输出的 node 本身就是 0 起始，直接给 CesiumMap 染色
        cesiumRef.value?.highlightSpreadNode?.(item.node);
      }

      currentIndex++;
    }, playSpeed);

  } catch (error) {
    console.error("模型运行失败:", error);
    ElMessage.error(error.response?.data?.message || "后端模型运行失败");
  } finally {
    isSpreadLoading.value = false;
  }
}

// 新增：恢复初始状态函数
function resetSpread() {
  // 1. 清除定时器停止播放
  if (spreadTimer) {
    clearInterval(spreadTimer);
    spreadTimer = null;
  }
  // 2. 清理界面状态
  isSpreadLoading.value = false;
  spreadResult.value = null; // 隐藏底部的“推演完成”绿色提示框
  // 3. 调用 CesiumMap 组件的重置方法，将节点恢复为默认的薄荷绿
  cesiumRef.value?.resetSpreadVisualization?.();
  
  ElMessage.info("已停止播放并恢复初始状态");
}

/* --- 左侧所有一级菜单的折叠状态（true = 展开） --- */
const collapse = reactive({
  bridgeList: true,   // 📋 桥梁选择列表
  gnnOld: true,      // ⚡ 单点 GNN（旧版，默认收起）
  gnnNew: true,       // 🚦 V-STGRN（新版，默认展开）
});
function togglePanel(key) {
  collapse[key] = !collapse[key];
}

/* --- 预测面板 --- */

/* --- 桥梁选择下拉（可搜索+remote）→ 必须放在 watch(currentBridge) 之前（immediate: true 会立刻引用） --- */
const bridgePickerId = ref(null);
const bridgePickerLoading = ref(false);
const bridgePickerOptions = ref([]);

watch(bridges, (list) => {
  /* 默认把所有桥梁放进下拉选项里，不用 remote 也能点一下展开全部 */
  bridgePickerOptions.value = list;
}, { immediate: true });

/* 切换桥梁时：同步下拉选择器 */
watch(currentBridge, (b) => {
  if (!b) {
    bridgePickerId.value = null;
    return;
  }
  bridgePickerId.value = Number(b.id);
}, { immediate: true });

function bridgeRemoteSearch(q) {
  if (!q) { bridgePickerOptions.value = bridges.value; return; }
  bridgePickerLoading.value = true;
  try {
    const kw = String(q).trim().toLowerCase();
    if (!kw) { bridgePickerOptions.value = bridges.value; return; }
    bridgePickerOptions.value = bridges.value.filter((b) => {
      const seqNo = String(b._displayIdx || 0);
      return seqNo === kw || String(b.name || "").toLowerCase().includes(kw);
    });
  } finally {
    setTimeout(() => { bridgePickerLoading.value = false; }, 120);
  }
}

function onBridgePickerChange(newId) {
  if (newId == null) return;
  searchKeyword.value = "";
  searchResults.value = [];
  const b = bridges.value.find((x) => Number(x.id) === Number(newId));
  if (b) selectBridge(b);
}

onMounted(async () => {
  // 刷新页面后若有本地已有 token，自动拉取列表并加载路网连线
  if (auth.token) {
    await loadBridges();
  }
});

async function handleLogin() {
  try {
    await auth.login(loginForm.username, loginForm.password);
    ElMessage.success("登录成功");
    // 登录后 Vue 需要重新渲染挂载 CesiumMap（v-if/v-else 切换）
    await nextTick();
    await loadBridges();
    // 等待 CesiumMap 组件挂载完成且 Viewer 初始化
    for (let i = 0; i < 30 && !cesiumRef.value; i++) {
      await new Promise((r) => setTimeout(r, 200));
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "登录失败");
  }
}

async function loadBridges() {
  try {
    const { data } = await client.get("/bridges", { params: query });
    let records = data.records || [];
    console.log("Loaded bridges:", records.length);
    // 为每条记录预计算显示序号（保持后端 node_0base 原始排序）
    records.forEach((r, i) => { r._displayIdx = i + 1; });
    bridges.value = records;
    console.log(`Successfully loaded ${records.length} bridges from backend.`);
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "查询失败");
  }
}

/* --- 搜索/查询逻辑 --- */
function handleSearch() {
  const kw = String(searchKeyword.value || "").trim().toLowerCase();
  searchResults.value = []; // 先清空之前的搜索结果

  if (!kw) {
    ElMessage.warning("请输入搜索关键词");
    return;
  }

  // 前端过滤：匹配序号（_displayIdx）或桥梁名称，收集所有匹配结果
  const matches = bridges.value.filter((b) => {
    const seqNo = String(b._displayIdx || 0);
    return seqNo === kw || String(b.name || "").toLowerCase().includes(kw);
  });

  if (matches.length === 0) {
    ElMessage.warning("未找到匹配的桥梁");
    return;
  }

  if (matches.length === 1) {
    // 单结果：直接跳转
    selectBridge(matches[0]);
    searchKeyword.value = ""; // 清空搜索框
  } else {
    // 多结果：展示结果面板供用户选择
    searchResults.value = matches;
  }
}

/* 联想建议查询（el-autocomplete 回调） */
function searchQuerySuggestions(queryStr, cb) {
  const kw = String(queryStr || "").trim().toLowerCase();
  if (!kw) { cb([]); return; }
  const matches = bridges.value.filter((b) => {
    const seqNo = String(b._displayIdx || 0);
    return seqNo === kw || String(b.name || "").toLowerCase().includes(kw);
  }).slice(0, 10); // 最多显示 10 条建议
  cb(matches);
}

/* 联想建议选中回调 */
function onSearchSuggestionSelect(item) {
  searchKeyword.value = ""; // 清空搜索框
  searchResults.value = []; // 清空多结果面板
  selectBridge(item);
}

/* 搜索结果面板点击 */
function onSearchResultClick(bridge) {
  searchResults.value = []; // 收起面板
  searchKeyword.value = ""; // 清空搜索框
  selectBridge(bridge);
}

/* 选中桥梁 → 聚焦跳转 + 详情滚动 + 加载动画 */
async function selectBridge(row) {
  if (!row) {
    ElMessage.warning("未选中有效桥梁");
    return;
  }
  selectedBridge.value = row;
  currentBridge.value = row; // 触发 CesiumMap watcher → flyToBridge

  // 加载动画：标记跳转中，等待 Cesium 飞行完成
  flyingToBridge.value = true;
  await new Promise((resolve) => setTimeout(resolve, 1800)); // Cesium flyTo 约 1500ms
  flyingToBridge.value = false;

  // 平滑滚动到桥梁详情区域
  const detailEl = document.getElementById("bridge-detail-section");
  if (detailEl) {
    detailEl.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

/* 单独按钮：查看当前选中桥梁的折线图弹窗（不触发定位/模型加载） */
function viewBridgeChart() {
  const row = currentBridge.value;
  if (!row) {
    ElMessage.warning("请先在列表中选择一座桥梁");
    return;
  }
  const arrayIndex = bridges.value.findIndex((b) => b.id === row.id);
  const node0Base =
    row && row.node_0base != null && !Number.isNaN(Number(row.node_0base))
      ? Number(row.node_0base)
      : arrayIndex >= 0
        ? Number(arrayIndex)
        : -1;
  try {
    trafficInfRef.value?.openBridgeChart?.({ bridge: row, arrayIndex, node0Base });
  } catch (e) {
    console.warn("[openBridgeChart] 调用失败:", e.message);
  }
}

/* 从 CesiumMap 点击节点 → 独立执行：飞到节点 + 加载模型 + 打开图表（不影响侧栏/下拉/搜索） */
async function handleBridgeClickWithIndex({ bridge, arrayIndex, node0Base }) {
  // 不再设置 currentBridge，地图点击与列表/搜索完全独立
  try {
    cesiumRef.value?.flyToBridge?.(bridge, 1200);
  } catch (_e) { /* ignore */ }
  try {
    const { data } = await client.get(`/models/${bridge.code}/tileset`);
    modelUrl.value = data.tilesetUrl;
  } catch (_e) { modelUrl.value = ""; }
  try {
    trafficInfRef.value?.openBridgeChart?.({
      bridge,
      arrayIndex,
      node0Base: Number.isFinite(node0Base) ? node0Base : undefined,
    });
  } catch (e) {
    console.warn("[openBridgeChart] 调用失败:", e.message);
  }
}

function handleGnnUpdate(stepData) {
  cesiumRef.value?.updateGnnVisualization(stepData);
}
</script>

<style scoped>
.page {
  height: 100vh;
  background: radial-gradient(900px 500px at 15% 0%, #0b3a6a 0%, rgba(11, 58, 106, 0) 60%),
    radial-gradient(900px 500px at 85% 0%, #1b2a4a 0%, rgba(27, 42, 74, 0) 60%),
    linear-gradient(180deg, #0b1220 0%, #070b14 100%);
}
.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  /* 👇 使用 .glass-panel 的样式属性 */
  background: rgba(30, 41, 59, 0.88);
  border-bottom: 1px solid rgba(16, 185, 129, 0.22);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.logout-link {
  color: rgba(226, 232, 240, 0.7);
  margin-left: 12px;
}
.logout-link:hover {
  color: #f87171;
}
.login-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(2, 6, 23, 0.85);
  backdrop-filter: blur(8px);
}
.login-card {
  width: 400px;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  overflow: hidden;
  padding: 30px;
}
.login-header {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 30px;
}
.login-body :deep(.el-form-item__label) {
  color: #94a3b8;
  font-weight: 500;
}
.login-body :deep(.el-input__wrapper) {
  background: rgba(30, 41, 59, 0.5);
  box-shadow: none;
  border: 1px solid rgba(148, 163, 184, 0.2);
}
.login-body :deep(.el-input__inner) {
  color: #f1f5f9;
}
.login-btn {
  width: 100%;
  height: 42px;
  font-weight: 600;
  margin-top: 10px;
  background: linear-gradient(135deg, #38BDF8, #10B981);
  border: none;
}
.login-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-weight: 800;
  letter-spacing: 0.5px;
  color: #e2e8f0;
  background: linear-gradient(135deg, rgba(56, 189, 248, 0.9), rgba(16, 185, 129, 0.75));
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
}
.titles .title {
  color: #e2e8f0;
  font-weight: 700;
  font-size: 16px;
  line-height: 18px;
}
.titles .subtitle {
  color: rgba(226, 232, 240, 0.7);
  font-size: 12px;
  margin-top: 2px;
}
.layout {
  height: calc(100vh - 56px);
}
.panel {
  position: relative;
  padding: 12px;
  border-right: 1px solid rgba(148, 163, 184, 0.18);
  overflow: auto;
  background: rgba(2, 6, 23, 0.55);
}
.sidebar-resizer {
  position: absolute;
  top: 0;
  right: 0;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  z-index: 30;
  transition: background 0.15s ease;
}
.sidebar-resizer:hover,
.sidebar-resizer:active {
  background: rgba(56, 189, 248, 0.35);
}
.panel-title {
  color: #e2e8f0;
  font-weight: 700;
  margin: 6px 0 10px;
}
.map-main {
  padding: 0;
}
.map-wrap {
  height: 100%;
  position: relative;
}
.hud {
  position: absolute;
  right: 12px;          /* 靠右 12px */
  top: 12px;            /* 👇 改回靠上 12px */
  bottom: auto;         /* 👇 清除底部定位 */
  width: 200px;         /* 保持缩小的宽度 */
  padding: 8px 10px;    
  border-radius: 8px;   
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(2, 6, 23, 0.65);
  color: rgba(226, 232, 240, 0.85);
  backdrop-filter: blur(10px);
  z-index: 10;
}

.hud-title {
  font-weight: 700;
  color: #e2e8f0;
  margin-bottom: 4px;   /* 缩小底部间距 */
  font-size: 13px;      /* 缩小标题字号 */
}

.hud-line {
  display: flex;
  align-items: center;  /* 保证下拉框和文字垂直居中对齐 */
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;      /* 缩小文字字号 */
  margin-top: 4px;
}

.hud-line .k {
  color: rgba(226, 232, 240, 0.6);
  white-space: nowrap;
}

.hud-line .v {
  color: rgba(226, 232, 240, 0.9);
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 覆盖面板里的 select 宽度 */
.hud-line :deep(.el-select) {
  width: 100px !important; /* 下拉框也跟着变窄 */
}

/* ================================================================
   左侧栏 sidebar-wrap：全模块统一间距
   ================================================================ */
.sidebar-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ================================================================
   玻璃容器 + 可折叠一级菜单（与 TrafficInference 风格一致）
   ================================================================ */
.glass-panel {
  background: rgba(30, 41, 59, 0.88);
  border: 1px solid rgba(16, 185, 129, 0.22);
  border-radius: 8px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  overflow: hidden;
}
.collapsible-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 13px;
  cursor: pointer;
  user-select: none;
  background: linear-gradient(90deg,
    rgba(16, 185, 129, 0.08) 0%,
    rgba(56, 189, 248, 0.05) 100%);
  border-bottom: 1px solid rgba(100, 116, 139, 0.18);
  transition: background 0.18s ease;
}
.collapsible-header:hover {
  background: linear-gradient(90deg,
    rgba(16, 185, 129, 0.16) 0%,
    rgba(56, 189, 248, 0.10) 100%);
}
.collapsible-body {
  padding: 14px;
  animation: fadeInCollapse 0.22s ease;
}
@keyframes fadeInCollapse {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
.menu-chevron {
  width: 0; height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 7px solid #94A3B8;
  display: inline-block;
  transform: rotate(-90deg);
  transition: transform 0.22s ease, border-color 0.18s ease;
  flex-shrink: 0;
  margin-left: 2px;
}
.menu-chevron.open {
  transform: rotate(0deg);
  border-top-color: #10B981;
}
.collapsible-header:hover .menu-chevron { border-top-color: #CBD5E1; }
.collapsible-header:hover .menu-chevron.open { border-top-color: #34D399; }

.menu-title {
  font-size: 14px; font-weight: 700; color: #E2E8F0;
  flex: 1; letter-spacing: 0.5px;
}
.menu-tag {
  padding: 1px 8px; border-radius: 4px; font-size: 11px;
  font-weight: 700; color: #ECFDF5;
  background: linear-gradient(90deg, #10B981, #059669);
}
.pred-tag { background: linear-gradient(90deg, #0EA5E9, #38BDF8); }
.tag-amber { background: linear-gradient(90deg, #0284C7, #38BDF8); }
.tag-admin { background: linear-gradient(90deg, #B91C1C, #EF4444); }

.menu-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  background: rgba(56, 189, 248, 0.15);
  color: #38BDF8;
  border: 1px solid rgba(56, 189, 248, 0.35);
  font-weight: 700; letter-spacing: 0.5px;
}

/* ================================================================
   📋 桥梁选择列表：下拉选择器 + switch 同一行
   ================================================================ */
.bridge-picker-row {
  margin-bottom: 2px;
}
.bridge-picker :deep(.el-select__wrapper) {
  background: rgba(15, 23, 42, 0.75) !important;
  border: 1px solid rgba(56, 189, 248, 0.32) !important;
  box-shadow: none !important;
  border-radius: 8px;
  height: 40px;
  color: #E2E8F0;
}
.bridge-picker :deep(.el-select__placeholder) {
  color: rgba(148, 163, 184, 0.78);
  font-size: 13px;
}
.bridge-picker :deep(.el-input__inner) {
  color: #E2E8F0;
  font-size: 13px;
}
.bridge-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
}
.bridge-option .b-code {
  color: #38BDF8;
  font-weight: 700;
  font-family: Consolas, monospace;
  font-size: 12px;
  min-width: 60px;
  display: inline-block;
}
.bridge-option .b-name {
  color: #E2E8F0;
  font-size: 13px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bridge-option .b-dist {
  color: rgba(148, 163, 184, 0.75);
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(30, 41, 59, 0.7);
  border: 1px solid rgba(100, 116, 139, 0.25);
}

/* 点显示 / 名显示 / 节点序号 → 同一行三列 */
.switch-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
  margin-top: 12px;
  padding: 9px 12px;
  background: rgba(2, 6, 23, 0.48);
  border: 1px solid rgba(100, 116, 139, 0.26);
  border-radius: 8px;
}
.switch-item {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.switch-item :deep(.el-switch__label) {
  font-size: 12px;
  color: #94A3B8;
  font-weight: 600;
}
.switch-item :deep(.is-active .el-switch__label) {
  color: #10B981;
}

/* =========================================================
   搜索结果面板 + 过渡动画
   ========================================================= */
.search-results-panel {
  margin-top: 10px;
  max-height: 260px;
  overflow-y: auto;
  background: rgba(10, 18, 36, 0.95);
  border: 1px solid rgba(56, 189, 248, 0.3);
  border-radius: 8px;
  padding: 6px 0;
}
.search-results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  font-size: 12px;
  color: #94A3B8;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  margin-bottom: 4px;
}
.search-results-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s ease;
}
.search-results-item:hover {
  background: rgba(56, 189, 248, 0.12);
}
.search-results-item.active {
  background: rgba(16, 185, 129, 0.12);
  color: #00FFAA;
}
.search-results-item .b-code {
  color: #38BDF8;
  font-size: 12px;
  min-width: 36px;
}
.search-results-item .b-name {
  color: #E2E8F0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.search-results-item .b-dist {
  color: rgba(148, 163, 184, 0.7);
  font-size: 11px;
}

/* slide-down 过渡动画 */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
  max-height: 260px;
  overflow: hidden;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
  margin-top: 0;
  border-width: 0;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
  margin-top: 0;
  border-width: 0;
}

/* =========================================================
   深色磨砂：蔓延预测数字输入框与下拉选择框
   ========================================================= */
:deep(.el-input-number .el-input__wrapper),
:deep(.el-select__wrapper) {
  background-color: rgba(11, 18, 33, 0.95) !important;
  border: 1px solid rgba(16, 185, 129, 0.4) !important;
  box-shadow: none !important;
  border-radius: 6px !important;
}

:deep(.el-input-number .el-input__wrapper:hover),
:deep(.el-select__wrapper:hover),
:deep(.el-input-number .el-input__wrapper.is-focus),
:deep(.el-select__wrapper.is-focused) {
  border-color: #10B981 !important;
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.35) !important;
}

:deep(.el-input-number .el-input__inner),
:deep(.el-select__selected-item),
:deep(.el-select__placeholder) {
  color: #E2E8F0 !important;
}

:deep(.el-input-number__decrease),
:deep(.el-input-number__increase) {
  background: rgba(30, 41, 59, 0.75) !important;
  color: #94A3B8 !important;
  border-left: 1px solid rgba(16, 185, 129, 0.25) !important;
  border-bottom: 1px solid rgba(16, 185, 129, 0.15) !important;
}

:deep(.el-input-number__decrease:hover),
:deep(.el-input-number__increase:hover) {
  color: #10B981 !important;
  background: rgba(16, 185, 129, 0.2) !important;
}
</style>

<style>
/* =========================================================
   全局字体 + Element Plus 绿色主题
   ========================================================= */
:root {
  --el-color-primary: #10B981;
  --el-color-primary-light-3: #34D399;
  --el-color-primary-light-5: #6EE7B7;
  --el-color-primary-light-7: #A7F3D0;
  --el-color-primary-light-8: #D1FAE5;
  --el-color-primary-light-9: #ECFDF5;
  --el-color-primary-dark-2: #059669;
}
html, body, #app {
  font-family: "Inter", "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei", "Segoe UI", system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
.mono, code, .el-input-number input {
  font-family: "JetBrains Mono", "SF Mono", "Consolas", "Courier New", monospace;
}
/* el-switch 绿色激活态 */
.el-switch.is-checked .el-switch__core {
  background-color: #10B981 !important;
  border-color: #10B981 !important;
}

/* =========================================================
   桥梁选择下拉面板：科幻深色 + 翡翠绿/星空蓝发光
   ========================================================= */
.bridge-picker-popper.el-select-dropdown {
  background: rgba(10, 18, 36, 0.97) !important;
  border: 1px solid rgba(56, 189, 248, 0.35) !important;
  border-radius: 10px !important;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.65), 0 0 24px rgba(56, 189, 248, 0.16) !important;
  backdrop-filter: blur(12px);
  overflow: hidden;
}
.bridge-picker-popper .el-select-dropdown__item {
  color: #E2E8F0;
  font-size: 13px;
  height: 38px;
  line-height: 38px;
  padding: 0 14px;
  transition: background 0.15s ease, color 0.15s ease;
}
.bridge-picker-popper .el-select-dropdown__item.is-hovering,
.bridge-picker-popper .el-select-dropdown__item:hover {
  background: rgba(56, 189, 248, 0.12);
}
.bridge-picker-popper .el-select-dropdown__item.is-selected,
.bridge-picker-popper .el-select-dropdown__item.selected {
  color: #00FFAA;
  background: rgba(16, 185, 129, 0.10);
  font-weight: 700;
}
.bridge-picker-popper .el-popper__arrow::before {
  background: rgba(10, 18, 36, 0.97) !important;
  border-color: rgba(56, 189, 248, 0.35) !important;
}
.bridge-picker-popper .el-scrollbar__bar.is-vertical .el-scrollbar__thumb {
  background: rgba(56, 189, 248, 0.4);
}
.bridge-picker-popper .bridge-option .b-code { color: #38BDF8; }
.bridge-picker-popper .bridge-option .b-name { color: #E2E8F0; }
.bridge-picker-popper .bridge-option .b-dist { color: rgba(148, 163, 184, 0.78); }

/* =========================================================
   顶部视图切换：科幻发光按钮 + 图标排布
   ========================================================= */
.view-switch .el-radio-button__inner {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(56, 189, 248, 0.28);
  color: #94A3B8;
  box-shadow: none;
  transition: all 0.2s ease;
}
.view-switch .el-radio-button__inner:hover {
  color: #E2E8F0;
  border-color: rgba(0, 255, 170, 0.5);
}
.view-switch .el-radio-button.is-active .el-radio-button__inner {
  background: linear-gradient(90deg, rgba(16, 185, 129, 0.9), rgba(8, 145, 178, 0.9));
  border-color: rgba(0, 255, 170, 0.6);
  color: #fff;
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.45);
}
.view-switch .el-radio-button + .el-radio-button {
  margin-left: -1px;
}

/* =========================================================
   搜索栏 & 按钮：科技黑风格（消除白色背景）
   ========================================================= */
/* 搜索输入框 - 科技深色 + 绿色边框 */
.glass-panel .el-input__wrapper {
  background: rgba(11, 18, 33, 0.95) !important;
  border: 1px solid rgba(16, 185, 129, 0.4) !important;
  box-shadow: none !important;
  border-radius: 6px !important;
}
.glass-panel .el-input__inner {
  color: #E2E8F0 !important;
  background: transparent !important;
}
.glass-panel .el-input__inner::placeholder {
  color: rgba(148, 163, 184, 0.6) !important;
}
/* 查询按钮 - 绿色主色调 */
.glass-panel .el-button--primary {
  background: #10B981 !important;
  border-color: rgba(16, 185, 129, 0.6) !important;
  color: #fff !important;
  border-radius: 6px !important;
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.35) !important;
}
.glass-panel .el-button--primary:hover {
  background: #059669 !important;
  border-color: #10B981 !important;
  box-shadow: 0 0 18px rgba(16, 185, 129, 0.5) !important;
}
/* 普通按钮 - 绿色边框 + 深色背景 */
.glass-panel .el-button--default,
.glass-panel .el-button {
  background: rgba(16, 185, 129, 0.15) !important;
  border-color: rgba(16, 185, 129, 0.5) !important;
  color: #10B981 !important;
  border-radius: 6px !important;
}
.glass-panel .el-button--default:hover,
.glass-panel .el-button:hover {
  background: rgba(16, 185, 129, 0.25) !important;
  border-color: #10B981 !important;
  color: #34D399 !important;
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.3) !important;
}
/* 查看折线图按钮 - 绿色 */
.chart-btn {
  background: rgba(16, 185, 129, 0.15) !important;
  border: 1px solid rgba(16, 185, 129, 0.5) !important;
  color: #10B981 !important;
  border-radius: 6px !important;
  font-weight: 600;
  transition: all 0.2s ease;
}
.chart-btn:hover {
  background: rgba(16, 185, 129, 0.3) !important;
  border-color: #10B981 !important;
  color: #34D399 !important;
  box-shadow: 0 0 14px rgba(16, 185, 129, 0.3) !important;
}
/* switch 未选中状态 - 深色 + 绿色边框 */
.glass-panel .el-switch__core {
  background: rgba(11, 18, 33, 0.9) !important;
  border-color: rgba(16, 185, 129, 0.3) !important;
}

/* =========================================================
   搜索联想弹出层样式（全局，因为 popper 渲染在 body）
   ========================================================= */
.search-suggest-popper {
  background: rgba(10, 18, 36, 0.98) !important;
  border: 1px solid rgba(56, 189, 248, 0.3) !important;
  border-radius: 8px !important;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4) !important;
  padding: 4px 0 !important;
}
.search-suggest-popper .el-autocomplete-suggestion__wrap {
  padding: 0 !important;
}
.search-suggest-popper .el-autocomplete-suggestion__list {
  padding: 0 !important;
}
.search-suggest-popper li {
  padding: 0 !important;
  border-bottom: none !important;
  transition: background 0.15s ease;
}
.search-suggest-popper li:hover {
  background: rgba(56, 189, 248, 0.12) !important;
}
.search-suggest-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 13px;
}
.search-suggest-item .b-code {
  color: #38BDF8;
  font-size: 12px;
  min-width: 36px;
}
.search-suggest-item .b-name {
  color: #E2E8F0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.search-suggest-item .b-dist {
  color: rgba(148, 163, 184, 0.7);
  font-size: 11px;
}
.search-suggest-item .b-dist {
  color: rgba(148, 163, 184, 0.7);
  font-size: 11px;
}

/* =========================================================
   全局：下拉菜单弹出面板（消除白色弹窗）
   ========================================================= */
.el-select__popper.el-popper {
  background: rgba(10, 18, 36, 0.98) !important;
  border: 1px solid rgba(16, 185, 129, 0.35) !important;
  border-radius: 8px !important;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.6) !important;
}

.el-select-dropdown__item {
  color: #E2E8F0 !important;
}

.el-select-dropdown__item.is-hovering,
.el-select-dropdown__item:hover {
  background: rgba(16, 185, 129, 0.15) !important;
  color: #34D399 !important;
}

.el-select-dropdown__item.is-selected {
  color: #00FFAA !important;
  font-weight: 700 !important;
  background: rgba(16, 185, 129, 0.1) !important;
}

.el-popper__arrow::before {
  background: rgba(10, 18, 36, 0.98) !important;
  border-color: rgba(16, 185, 129, 0.35) !important;
}
</style>