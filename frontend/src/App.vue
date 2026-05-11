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
            <div class="subtitle">群桥展示 · 查询 · 管理（轻量版）</div>
          </div>
        </div>
        <div class="top-actions">
          <el-tag type="success" effect="dark">已登录：{{ auth.user?.username }}</el-tag>
          <el-button link class="logout-link" @click="auth.logout()">退出登录</el-button>
        </div>
      </header>

      <el-container class="layout">
        <el-aside width="380px" class="panel">
          <div>
            <div class="panel-title">桥梁检索</div>
            <el-space wrap>
              <el-input
                v-model="query.keyword"
                placeholder="桥名/编码搜索"
                style="width: 240px;"
                clearable
                @keyup.enter="handleSearch"
              />
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button :disabled="!bridges.length" @click="locateFirst">定位首条</el-button>
              <el-button
                type="warning"
                plain
                :disabled="!currentBridge"
                @click="togglePickMode"
              >
                {{ pickMode ? "退出校准" : "点选校准" }}
              </el-button>
              <el-switch
                v-model="showAllPoints"
                active-text="点显示"
                inactive-text="点隐藏"
                style="margin-left: 10px;"
              />
              <el-switch
                v-model="showAllLabels"
                active-text="名显示"
                inactive-text="名隐藏"
                style="margin-left: 10px;"
              />
            </el-space>

            <el-table :data="bridges" height="420" style="margin-top:12px;" @row-click="selectBridge">
              <el-table-column prop="code" label="编码" width="90" />
              <el-table-column prop="name" label="桥梁名称" />
              <el-table-column prop="district" label="区域" width="90" />
            </el-table>

            <!-- 健康监测看板 -->
            <HealthDashboard :bridge="currentBridge" />

            <!-- GNN 流量推演面板 -->
            <GnnDeduction :current-bridge="currentBridge" @update-gnn="handleGnnUpdate" />

            <div class="panel-title" style="margin-top: 14px;">样式/预览（Three.js）</div>
            <div class="three-card">
              <ThreeScene />
              <div class="three-caption">
                这里用于后续扩展：桥梁构件样式、材质预览、剖切/标注等 Three 可视化能力。
              </div>
            </div>

            <div v-if="auth.user?.role === 'admin'" class="admin-section">
              <div class="panel-title" style="margin-top: 20px; color: #fbbf24;">系统管理</div>
              <div class="admin-tools">
                <el-button type="danger" plain size="small" :loading="syncing" @click="handleSyncData">
                  同步 Excel 数据
                </el-button>
                <div v-if="currentBridge" class="model-bind-tool">
                  <div class="small-label">绑定 3D 模型路径:</div>
                  <el-input
                    v-model="currentBridge.model_path"
                    placeholder="/models/CODE/tileset.json"
                    size="small"
                  >
                    <template #append>
                      <el-button @click="handleBindModel">保存</el-button>
                    </template>
                  </el-input>
                </div>
              </div>
            </div>
          </div>
        </el-aside>

        <el-main class="map-main">
          <div class="map-wrap">
            <CesiumMap
              ref="cesiumRef"
              :current-bridge="currentBridge"
              :bridges="bridges"
              :show-all-points="showAllPoints"
              :show-all-labels="showAllLabels"
              :map-mode="mapMode"
              :model-url="modelUrl"
              :pick-mode="pickMode"
              @picked="handlePicked"
            />

            <div class="hud">
            <div class="hud-title">地图视图</div>
            <div class="hud-line">
              <span class="k">地图模式</span>
              <el-select v-model="mapMode" size="small" style="width: 100px;">
                <el-option label="卫星影像" value="satellite" />
                <el-option label="标准街道" value="street" />
                <el-option label="极夜黑" value="dark" />
                <el-option label="浅色底图" value="light" />
              </el-select>
            </div>
            <div class="hud-line">
              <span class="k">当前桥梁</span>
              <span class="v">{{ currentBridge?.name || "未选择" }}</span>
            </div>
              <div class="hud-line">
                <span class="k">校准</span>
                <span class="v">{{ pickMode ? "请在地图上单击真实位置" : "关闭" }}</span>
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
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import client from "./api/client";
import { useAuthStore } from "./stores/auth";
import CesiumMap from "./components/CesiumMap.vue";
import ThreeScene from "./components/ThreeScene.vue";
import HealthDashboard from "./components/HealthDashboard.vue";
import GnnDeduction from "./components/GnnDeduction.vue";
import { Loading, Share } from "@element-plus/icons-vue";

const auth = useAuthStore();
const loginForm = reactive({ username: "admin", password: "admin123" });
const query = reactive({ keyword: "", page: 1, pageSize: 500 });
const bridges = ref([]);
const currentBridge = ref(null);
const modelUrl = ref("");
const cesiumRef = ref(null);
const pickMode = ref(false);
const showAllPoints = ref(true);
const showAllLabels = ref(true);
const mapMode = ref("satellite");
const syncing = ref(false);

onMounted(() => {
  // 刷新页面后如果本地已有 token，自动拉取一次列表，避免出现 “No Data” 误解为未连接
  if (auth.token) loadBridges();
});

async function handleLogin() {
  try {
    await auth.login(loginForm.username, loginForm.password);
    ElMessage.success("登录成功");
    await loadBridges();
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "登录失败");
  }
}

async function loadBridges() {
  try {
    const { data } = await client.get("/bridges", { params: query });
    let records = data.records || [];
    console.log("Loaded bridges:", records.length);
    // 优先将杨浦大桥排在首位
    records.sort((a, b) => {
      const nameA = a.name || "";
      const nameB = b.name || "";
      if (nameA.includes("杨浦大桥")) return -1;
      if (nameB.includes("杨浦大桥")) return 1;
      return 0;
    });
    bridges.value = records;
    console.log(`Successfully loaded ${records.length} bridges from backend.`);
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "查询失败");
  }
}

async function handleSearch() {
  query.page = 1;
  await loadBridges();
}

function locateFirst() {
  if (!bridges.value.length) return;
  // 直接查找列表中的杨浦大桥，确保定位准确
  const yangpu = bridges.value.find(b => b.name.includes("杨浦大桥"));
  if (yangpu) {
    selectBridge(yangpu);
  } else {
    selectBridge(bridges.value[0]);
  }
}

async function selectBridge(row) {
  currentBridge.value = row;
  // 立即定位
  try {
    cesiumRef.value?.flyToBridge?.(row, 1200);
  } catch (_e) {
    // ignore
  }
  try {
    const { data } = await client.get(`/models/${row.code}/tileset`);
    modelUrl.value = data.tilesetUrl;
  } catch (_e) {
    modelUrl.value = "";
  }
}

function togglePickMode() {
  pickMode.value = !pickMode.value;
  if (pickMode.value) {
    ElMessage.warning("校准模式：请在地图上单击桥梁的真实位置（卫星图）");
  }
}

async function handlePicked(pos) {
  if (!pickMode.value) return;
  if (!currentBridge.value) return;
  try {
    await client.put(`/bridges/${currentBridge.value.id}/coords`, {
      lon: pos.lon,
      lat: pos.lat,
    });
    ElMessage.success("坐标已校准并保存");
    pickMode.value = false;
    await loadBridges();
    // 重新选中当前桥，触发定位
    const updated = bridges.value.find((b) => b.id === currentBridge.value.id);
    if (updated) await selectBridge(updated);
  } catch (e) {
    ElMessage.error(e.response?.data?.message || "校准保存失败（需要管理员权限）");
  }
}

async function handleSyncData() {
  try {
    syncing.value = true;
    await client.post("/admin/sync-pois");
    ElMessage.success("数据同步成功");
    await loadBridges();
  } catch (e) {
    // 拦截器已处理错误显示
  } finally {
    syncing.value = false;
  }
}

async function handleBindModel() {
  if (!currentBridge.value) return;
  try {
    await client.put(`/admin/bridges/${currentBridge.value.id}/model`, {
      modelPath: currentBridge.value.model_path,
    });
    ElMessage.success("模型绑定成功");
    modelUrl.value = currentBridge.value.model_path;
  } catch (e) {
    // 拦截器已处理错误显示
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
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  backdrop-filter: blur(10px);
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
  background: linear-gradient(135deg, #3b82f6, #10b981);
  border: none;
}
.login-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}
.admin-section {
  border-top: 1px dashed rgba(148, 163, 184, 0.3);
  padding-top: 10px;
}
.admin-tools {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.model-bind-tool {
  background: rgba(30, 41, 59, 0.3);
  padding: 10px;
  border-radius: 8px;
}
.small-label {
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 5px;
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
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.9), rgba(16, 185, 129, 0.75));
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
  padding: 12px;
  border-right: 1px solid rgba(148, 163, 184, 0.18);
  overflow: auto;
  background: rgba(2, 6, 23, 0.55);
}
.panel-title {
  color: #e2e8f0;
  font-weight: 700;
  margin: 6px 0 10px;
}
.three-card {
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  overflow: hidden;
  background: rgba(2, 6, 23, 0.45);
}
.three-card :deep(.root) {
  height: 220px;
}
.three-caption {
  padding: 10px 12px;
  color: rgba(226, 232, 240, 0.75);
  font-size: 12px;
  line-height: 18px;
  border-top: 1px solid rgba(148, 163, 184, 0.14);
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
  right: 12px;
  top: 12px;
  width: 260px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(2, 6, 23, 0.55);
  color: rgba(226, 232, 240, 0.85);
  backdrop-filter: blur(10px);
}
.hud-title {
  font-weight: 700;
  color: #e2e8f0;
  margin-bottom: 6px;
}
.hud-line {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  margin-top: 4px;
}
.hud-line .k {
  color: rgba(226, 232, 240, 0.6);
}
.hud-line .v {
  color: rgba(226, 232, 240, 0.9);
  text-align: right;
}
</style>
