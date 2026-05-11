<template>
  <div class="gnn-panel">
    <div class="panel-header">
      <el-icon><Share /></el-icon>
      <span>GNN 节点流量推演</span>
    </div>
    
    <div class="panel-body">
      <div v-if="currentBridge" class="target-info">
        已选中中心节点: <span class="highlight">{{ currentBridge.name }}</span>
      </div>
      <div v-else class="target-info warn">
        请先在左侧列表点击选择一个中心节点
      </div>

      <el-button 
        type="primary" 
        :loading="loading" 
        :disabled="!currentBridge"
        @click="startInference"
        style="width: 100%;"
      >
        {{ loading ? '算法推演中...' : (isPlaying ? '推演播放中...' : '开始以选中点推演') }}
      </el-button>

      <div v-if="result" class="result-info">
        <div class="step-control">
          <div class="step-label">
            <span>时间进度: {{ result.data[currentStep].time_label }}</span>
            <span>步数: {{ currentStep + 1 }} / {{ result.total_steps }}</span>
          </div>
          <el-slider 
            v-model="currentStep" 
            :max="result.total_steps - 1" 
            :step="1"
            @change="updateVisualization"
          />
        </div>
        <div class="legend">
          <div class="legend-item"><span class="line low"></span> 低流量 (&lt;60)</div>
          <div class="legend-item"><span class="line mid"></span> 中流量 (60-120)</div>
          <div class="legend-item"><span class="line high"></span> 高流量 (&gt;120)</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { Share } from '@element-plus/icons-vue';
import client from '../api/client';

const props = defineProps({
  currentBridge: { type: Object, default: null }
});

const loading = ref(false);
const result = ref(null);
const currentStep = ref(0);
const isPlaying = ref(false);
let playTimer = null;

const emitEvent = defineEmits(['update-gnn']);

const startInference = async () => {
  if (!props.currentBridge) return;
  
  // 清除之前的播放状态
  stopPlayback();
  
  loading.value = true;
  try {
    const { data } = await client.post('/gnn/inference', {
      bridgeCode: props.currentBridge.code
    });
    result.value = data;
    currentStep.value = 0;
    updateVisualization();
    
    // 自动开始播放
    startPlayback();
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const startPlayback = () => {
  if (!result.value) return;
  isPlaying.value = true;
  
  playTimer = setInterval(() => {
    if (currentStep.value < result.value.total_steps - 1) {
      currentStep.value++;
      updateVisualization();
    } else {
      stopPlayback();
    }
  }, 1000); // 每秒播放一步（代表真实世界 5 分钟）
};

const stopPlayback = () => {
  isPlaying.value = false;
  if (playTimer) {
    clearInterval(playTimer);
    playTimer = null;
  }
};

const updateVisualization = () => {
  if (!result.value) return;
  const stepData = result.value.data[currentStep.value];
  emitEvent('update-gnn', stepData);
};
</script>

<style scoped>
.gnn-panel {
  background: rgba(30, 41, 59, 0.88);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid rgba(16, 185, 129, 0.22);
  border-radius: 8px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.35);
  padding: 15px;
  margin-top: 15px;
}
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fbbf24;
  font-weight: 600;
  margin-bottom: 12px;
}
.target-info {
  font-size: 13px;
  color: #e2e8f0;
  margin-bottom: 12px;
  padding: 8px;
  background: rgba(56, 189, 248, 0.1);
  border-radius: 6px;
  border-left: 3px solid #38BDF8;
}
.target-info.warn {
  color: #ffffff;
  background: rgba(251, 191, 36, 0.1);
  border-left-color: #38BDF8;
}
.highlight {
  color: #38BDF8;
  font-weight: bold;
}
.result-info {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px dashed rgba(148, 163, 184, 0.2);
}
.step-control {
  font-size: 12px;
  color: #94a3b8;
}
.step-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
}
.legend {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 10px;
  color: #64748b;
}
.legend-item { display: flex; align-items: center; gap: 4px; }
.line { width: 12px; height: 2px; border-radius: 1px; }
.line.low { background: #10b981; }
.line.mid { background: #38BDF8; } /* 科技蓝 */
.line.high { background: #ef4444; }
</style>
