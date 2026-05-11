<template>
  <div class="health-dashboard">
    <div v-if="bridge">
      <div class="dashboard-header">
        <div class="title-group">
          <span class="status-dot" :class="status"></span>
          <span class="bridge-name">{{ bridge.name }} - 健康监测</span>
        </div>
        <el-tag :type="statusType" size="small" effect="dark">{{ statusText }}</el-tag>
      </div>

      <div class="charts-container">
        <div class="chart-item">
          <div class="chart-label">实时震动频率 (Hz)</div>
          <div ref="vibrationChartRef" class="chart-box"></div>
        </div>
        <div class="chart-item">
          <div class="chart-label">结构位移偏移 (mm)</div>
          <div ref="displacementChartRef" class="chart-box"></div>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">环境温度</div>
          <div class="stat-value">{{ temp.toFixed(1) }} °C</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">当前风速</div>
          <div class="stat-value">{{ wind.toFixed(1) }} m/s</div>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>请在上方列表选中桥梁以开启实时监测</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue';
import * as echarts from 'echarts';

const props = defineProps({
  bridge: { type: Object, default: null }
});

const vibrationChartRef = ref(null);
const displacementChartRef = ref(null);
let vibrationChart = null;
let displacementChart = null;
let timer = null;

const status = ref('normal');
const temp = ref(24.5);
const wind = ref(3.2);

const statusType = computed(() => {
  if (status.value === 'normal') return 'success';
  if (status.value === 'warning') return 'warning';
  return 'danger';
});

const statusText = computed(() => {
  if (status.value === 'normal') return '运行正常';
  if (status.value === 'warning') return '数据波动';
  return '结构预警';
});

// 模拟数据生成
const dataCount = 20;
const vibrationData = ref(new Array(dataCount).fill(0).map(() => Math.random() * 2 + 5));
const displacementData = ref(new Array(dataCount).fill(0).map(() => Math.random() * 1 + 2));
const timeline = ref(new Array(dataCount).fill(0).map((_, i) => `${i}s`));

const initCharts = () => {
  if (!vibrationChartRef.value || !displacementChartRef.value) return;

  const commonOption = {
    grid: { top: 10, bottom: 20, left: 30, right: 10 },
    xAxis: {
      type: 'category',
      data: timeline.value,
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
      axisLabel: { color: '#94a3b8', fontSize: 10 }
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'none',
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(59, 130, 246, 0.5)' },
          { offset: 1, color: 'rgba(59, 130, 246, 0)' }
        ])
      },
      lineStyle: { width: 2, color: '#3b82f6' }
    }]
  };

  vibrationChart = echarts.init(vibrationChartRef.value);
  displacementChart = echarts.init(displacementChartRef.value);

  vibrationChart.setOption({
    ...commonOption,
    series: [{ ...commonOption.series[0], data: vibrationData.value }]
  });

  displacementChart.setOption({
    ...commonOption,
    series: [{
      ...commonOption.series[0],
      data: displacementData.value,
      lineStyle: { width: 2, color: '#10b981' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(16, 185, 129, 0.5)' },
          { offset: 1, color: 'rgba(16, 185, 129, 0)' }
        ])
      }
    }]
  });
};

const updateData = () => {
  // 模拟数据滚动
  vibrationData.value.shift();
  vibrationData.value.push(Math.random() * 2 + 5 + (status.value === 'warning' ? 2 : 0));
  
  displacementData.value.shift();
  displacementData.value.push(Math.random() * 1 + 2 + (status.value === 'warning' ? 1 : 0));

  vibrationChart?.setOption({ series: [{ data: vibrationData.value }] });
  displacementChart?.setOption({ series: [{ data: displacementData.value }] });

  // 随机改变状态
  if (Math.random() > 0.95) {
    status.value = status.value === 'normal' ? 'warning' : 'normal';
  }
  
  temp.value += (Math.random() - 0.5) * 0.1;
  wind.value = Math.max(0, wind.value + (Math.random() - 0.5) * 0.2);
};

onMounted(() => {
  initCharts();
  timer = setInterval(updateData, 1000);
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  clearInterval(timer);
  window.removeEventListener('resize', handleResize);
  vibrationChart?.dispose();
  displacementChart?.dispose();
});

const handleResize = () => {
  vibrationChart?.resize();
  displacementChart?.resize();
};

watch(() => props.bridge, () => {
  if (vibrationChart) {
    vibrationData.value = new Array(dataCount).fill(0).map(() => Math.random() * 2 + 5);
    displacementData.value = new Array(dataCount).fill(0).map(() => Math.random() * 1 + 2);
  }
});
</script>

<style scoped>
.health-dashboard {
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  padding: 16px;
  margin-top: 16px;
  color: #f1f5f9;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 0 0 8px currentColor;
}
.status-dot.normal { color: #10b981; background: #10b981; }
.status-dot.warning { color: #f59e0b; background: #f59e0b; }
.status-dot.danger { color: #ef4444; background: #ef4444; }

.bridge-name {
  font-weight: 600;
  font-size: 14px;
}

.charts-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chart-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chart-label {
  font-size: 11px;
  color: #94a3b8;
}

.chart-box {
  height: 100px;
  width: 100%;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-label {
  font-size: 11px;
  color: #94a3b8;
}

.stat-value {
  font-weight: 700;
  font-size: 16px;
  color: #3b82f6;
}
.empty-state {
  height: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #94a3b8;
  font-size: 13px;
}
.empty-state .el-icon {
  font-size: 24px;
}
</style>
