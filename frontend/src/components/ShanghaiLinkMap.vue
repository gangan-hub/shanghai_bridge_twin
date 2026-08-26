<template>
  <div class="link-map-page">
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
import { ref, onMounted } from 'vue';
import { Loading } from '@element-plus/icons-vue';

const iframeUrl = '/shanghai-link-map.html';
const showFrame = ref(false);
const iframeRef = ref(null);

onMounted(() => {
  setTimeout(() => {
    showFrame.value = true;
  }, 300);
});
</script>

<style scoped>
.link-map-page {
  width: 100%;
  height: calc(100vh - 56px);
  display: flex;
  flex-direction: column;
  background: #070b14;
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
