<template>
  <div class="link-map-page">
    <div class="page-toolbar">
      <el-button :icon="Back" @click="$emit('back')" plain>
        返回地图
      </el-button>
      <div class="page-title">
        <el-icon :size="22" color="#38bdf8"><Connection /></el-icon>
        <h2>上海桥隧群空间网络拓扑地图</h2>
      </div>
      <div class="toolbar-right">
        <el-tag effect="dark" type="info" size="large">Leaflet 全量底图版</el-tag>
        <el-button 
          type="primary" 
          plain 
          :icon="RefreshRight" 
          size="default"
          @click="reloadIframe"
        >
          刷新地图
        </el-button>
        <el-button 
          type="success" 
          :icon="Aim" 
          size="default"
          @click="openNewTab"
        >
          新标签打开
        </el-button>
      </div>
    </div>
    <div class="iframe-container">
      <iframe
        v-if="showFrame"
        ref="iframeRef"
        :src="iframeUrl"
        class="map-iframe"
        frameborder="0"
        allowfullscreen
      ></iframe>
      <div v-else class="loading-placeholder">
        <el-icon class="loading-icon" :size="64" color="#38bdf8"><Loading /></el-icon>
        <div class="loading-text">正在加载空间网络拓扑地图...</div>
        <div class="loading-hint">首次加载约需 3-10 秒（含节点和路网数据）</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onBeforeUnmount, onMounted } from 'vue';
import { Back, RefreshRight, Aim, Connection, Loading } from '@element-plus/icons-vue';

defineEmits(['back']);

const iframeUrl = '/shanghai-link-map.html';
const showFrame = ref(false);
const iframeRef = ref(null);

onMounted(() => {
  setTimeout(() => {
    showFrame.value = true;
  }, 300);
});

function reloadIframe() {
  if (iframeRef.value) {
    showFrame.value = false;
    nextTick(() => {
      showFrame.value = true;
    });
  }
}

function openNewTab() {
  window.open(iframeUrl, '_blank', 'noopener,noreferrer');
}
</script>

<style scoped>
.link-map-page {
  width: 100%;
  height: calc(100vh - 56px);
  display: flex;
  flex-direction: column;
  background: #0b1220;
}
.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: rgba(15, 23, 42, 0.85);
  border-bottom: 1px solid rgba(56, 189, 248, 0.2);
  backdrop-filter: blur(10px);
}
.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #38bdf8;
  letter-spacing: 1px;
  background: linear-gradient(90deg, #00ffaa, #38bdf8);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.toolbar-right {
  display: flex;
  gap: 12px;
  align-items: center;
}
.iframe-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #070b14;
}
.map-iframe {
  width: 100%;
  height: 100%;
  border: none;
  display: block;
}
.loading-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 15px;
}
.loading-icon {
  animation: rotate 1.5s linear infinite;
}
@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.loading-text {
  color: #e2e8f0;
  font-size: 16px;
  font-weight: 500;
}
.loading-hint {
  color: #64748b;
  font-size: 12px;
}
</style>
