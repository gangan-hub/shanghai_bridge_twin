<template>
  <div class="deduction-page">
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="Back" @click="$emit('back')" plain>
          返回地图
        </el-button>
        <h2 class="page-title">
          <el-icon :size="22" color="#38BDF8"><TrendCharts /></el-icon>
          桥隧群流量推演中心
        </h2>
      </div>
      <div class="header-right">
        <el-tag effect="dark" type="success">AI 模型: V-STGRN</el-tag>
        <el-tag effect="dark" type="warning">节点: {{ totalNodes }}</el-tag>
      </div>
    </div>

    <div class="page-body">
      <div class="left-config">
        <div class="card">
          <div class="card-title">1. 选择推演中心节点</div>
          <el-select 
            v-model="selectedBridgeCode" 
            placeholder="选择中心桥梁" 
            filterable 
            style="width: 100%;"
          >
            <el-option
              v-for="b in bridges"
              :key="b.code"
              :label="`${b.name} (${b.code})`"
              :value="b.code"
            />
          </el-select>
          <div v-if="selectedBridge" class="selected-info">
            <div>当前中心: <b>{{ selectedBridge.name }}</b></div>
            <div>区域: {{ selectedBridge.district || '-' }}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">2. 推演参数</div>
          <el-form label-width="100px">
            <el-form-item label="推演步长">
              <el-select v-model="config.steps" style="width: 100%;">
                <el-option label="6 步 (30分钟)" :value="6" />
                <el-option label="12 步 (1小时)" :value="12" />
                <el-option label="24 步 (2小时)" :value="24" />
              </el-select>
            </el-form-item>
            <el-form-item label="攻击强度">
              <el-slider v-model="config.attackLevel" :min="1" :max="10" :marks="{1:'低',5:'中',10:'高'}" />
            </el-form-item>
            <el-form-item label="扩散模式">
              <el-radio-group v-model="config.diffusion">
                <el-radio value="linear">线性扩散</el-radio>
                <el-radio value="exponential">指数扩散</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>
          <el-button 
            type="primary" 
            :loading="running" 
            :disabled="!selectedBridgeCode"
            @click="runInference" 
            style="width: 100%; margin-top: 10px;"
            size="large"
          >
            {{ running ? '推演计算中...' : '🚀 开始推演' }}
          </el-button>
        </div>

        <div class="card">
          <div class="card-title">3. 推演概览</div>
          <div v-if="!result" class="empty-hint">
            暂无数据，请先执行推演
          </div>
          <div v-else class="stats">
            <div class="stat-item">
              <div class="stat-value red">{{ maxLoad.toFixed(1) }}%</div>
              <div class="stat-label">最大负载</div>
            </div>
            <div class="stat-item">
              <div class="stat-value orange">{{ avgLoad.toFixed(1) }}%</div>
              <div class="stat-label">平均负载</div>
            </div>
            <div class="stat-item">
              <div class="stat-value blue">{{ overloadCount }}</div>
              <div class="stat-label">过载节点</div>
            </div>
          </div>
        </div>
      </div>

      <div class="right-visual">
        <div class="card full-height">
          <div class="card-title-with-tabs">
            <span>4. 推演结果可视化</span>
            <div class="step-player" v-if="result">
              <el-button-group size="small">
                <el-button @click="prevStep" :disabled="currentStep <= 0">上一步</el-button>
                <el-button @click="togglePlay">
                  {{ playing ? '⏸ 暂停' : '▶ 播放' }}
                </el-button>
                <el-button @click="nextStep" :disabled="currentStep >= totalSteps - 1">下一步</el-button>
              </el-button-group>
              <el-slider 
                v-model="currentStep" 
                :max="totalSteps - 1" 
                :step="1"
                style="width: 280px; margin-left: 16px;"
                size="small"
                @change="updateCharts"
              />
              <span class="step-label">{{ currentTimeLabel }}</span>
            </div>
          </div>

          <div v-if="!result" class="empty-visual">
            <el-empty description="选择桥梁后点击开始推演，此处将展示结果" :image-size="160" />
          </div>

          <div v-else class="charts-area">
            <div class="charts-row">
              <div class="chart-box">
                <div class="chart-title">节点负载热力排行 (当前步)</div>
                <div ref="barChartRef" class="chart"></div>
              </div>
              <div class="chart-box">
                <div class="chart-title">全网负载分布 (当前步)</div>
                <div ref="pieChartRef" class="chart"></div>
              </div>
            </div>
            <div class="chart-box full-width">
              <div class="chart-title">Top-10 关键节点时序 (推演全程)</div>
              <div ref="lineChartRef" class="chart tall"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue';
import { Back, TrendCharts } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import * as echarts from 'echarts';
import client from '../api/client';

const props = defineProps({
  bridges: { type: Array, default: () => [] }
});

const emit = defineEmits(['back', 'update-gnn']);

const selectedBridgeCode = ref('');
const selectedBridge = computed(() => 
  props.bridges.find(b => b.code === selectedBridgeCode.value) || null
);
const totalNodes = ref(358);

const config = ref({
  steps: 12,
  attackLevel: 7,
  diffusion: 'linear'
});

const running = ref(false);
const result = ref(null);
const currentStep = ref(0);
const playing = ref(false);
let playTimer = null;

const totalSteps = computed(() => result.value?.total_steps || 0);
const currentTimeLabel = computed(() => result.value?.data?.[currentStep.value]?.time_label || '-');

const maxLoad = computed(() => {
  if (!result.value) return 0;
  const nodes = result.value.data[currentStep.value]?.nodes || {};
  return Math.max(...Object.values(nodes));
});
const avgLoad = computed(() => {
  if (!result.value) return 0;
  const nodes = result.value.data[currentStep.value]?.nodes || {};
  const vals = Object.values(nodes);
  return vals.reduce((a,b)=>a+b,0) / (vals.length || 1);
});
const overloadCount = computed(() => {
  if (!result.value) return 0;
  const nodes = result.value.data[currentStep.value]?.nodes || {};
  return Object.values(nodes).filter(v => v >= 80).length;
});

const barChartRef = ref(null);
const pieChartRef = ref(null);
const lineChartRef = ref(null);
let barChart = null, pieChart = null, lineChart = null;

onMounted(async () => {
  await nextTick();
  if (barChartRef.value) barChart = echarts.init(barChartRef.value);
  if (pieChartRef.value) pieChart = echarts.init(pieChartRef.value);
  if (lineChartRef.value) lineChart = echarts.init(lineChartRef.value);
  window.addEventListener('resize', handleResize);
});
onBeforeUnmount(() => {
  stopPlay();
  window.removeEventListener('resize', handleResize);
  barChart?.dispose(); pieChart?.dispose(); lineChart?.dispose();
});
function handleResize() {
  barChart?.resize(); pieChart?.resize(); lineChart?.resize();
}

async function runInference() {
  if (!selectedBridgeCode.value) return;
  running.value = true;
  stopPlay();
  try {
    const { data } = await client.post('/gnn/inference', {
      bridgeCode: selectedBridgeCode.value
    });
    result.value = data;
    currentStep.value = 0;
    ElMessage.success(`推演完成，共 ${data.total_steps} 个时间步`);
    nextTick(updateCharts);
  } catch (e) {
    ElMessage.error(e.response?.data?.message || '推演失败，请检查 FastAPI 服务');
  } finally {
    running.value = false;
  }
}

function updateCharts() {
  if (!result.value) return;
  const stepData = result.value.data[currentStep.value];
  const nodes = stepData.nodes || {};
  emit('update-gnn', stepData);
  renderBar(nodes);
  renderPie(nodes);
  renderLine();
}

function renderBar(nodes) {
  if (!barChart) return;
  const entries = Object.entries(nodes).sort((a,b) => b[1]-a[1]).slice(0, 15);
  barChart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 100, right: 20, top: 10, bottom: 30 },
    xAxis: { type: 'value', max: 100, axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    yAxis: { 
      type: 'category', 
      data: entries.map(e => e[0]).reverse(), 
      axisLabel: { color: '#cbd5e1', fontSize: 10 } 
    },
    series: [{
      type: 'bar',
      data: entries.map(e => ({
        value: e[1],
        itemStyle: { color: e[1] >= 80 ? '#ef4444' : e[1] >= 60 ? '#38BDF8' : '#10b981' }
      })).reverse(),
      barWidth: '60%',
      label: { show: true, position: 'right', color: '#e2e8f0', fontSize: 10, formatter: '{c}%' }
    }]
  });
}

function renderPie(nodes) {
  if (!pieChart) return;
  const vals = Object.values(nodes);
  const low = vals.filter(v => v < 60).length;
  const mid = vals.filter(v => v >= 60 && v < 80).length;
  const high = vals.filter(v => v >= 80).length;
  pieChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: '#cbd5e1' } },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '45%'],
      data: [
        { name: '低流量 <60%', value: low, itemStyle: { color: '#10b981' } },
        { name: '中流量 60~80%', value: mid, itemStyle: { color: '#38BDF8' } },
        { name: '高流量 ≥80%', value: high, itemStyle: { color: '#ef4444' } }
      ],
      label: { color: '#e2e8f0', fontSize: 11, formatter: '{b}\n{d}% ({c})' }
    }]
  });
}

function renderLine() {
  if (!lineChart || !result.value) return;
  const data = result.value.data;
  const timeLabels = data.map(s => s.time_label);
  const step0 = data[0].nodes || {};
  const topKeys = Object.entries(step0).sort((a,b)=>b[1]-a[1]).slice(0,10).map(e=>e[0]);
  const series = topKeys.map(key => {
    const color = key === selectedBridgeCode.value ? '#38BDF8' : null;
    return {
      name: key,
      type: 'line',
      smooth: true,
      data: data.map(s => (s.nodes[key] || 0).toFixed(1)),
      lineStyle: color ? { width: 3, color } : undefined,
      itemStyle: color ? { color } : undefined,
      symbol: 'circle',
      symbolSize: 5
    };
  });
  lineChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { 
      type: 'scroll', 
      bottom: 0, 
      textStyle: { color: '#cbd5e1' },
      pageTextStyle: { color: '#cbd5e1' }
    },
    grid: { left: 50, right: 30, top: 20, bottom: 60 },
    xAxis: { type: 'category', data: timeLabels, axisLabel: { color: '#94a3b8' } },
    yAxis: { type: 'value', name: '负载 %', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1e293b' } }, nameTextStyle: { color: '#94a3b8' } },
    series
  });
}

function prevStep() { if (currentStep.value > 0) { currentStep.value--; updateCharts(); } }
function nextStep() { if (currentStep.value < totalSteps.value - 1) { currentStep.value++; updateCharts(); } }
function togglePlay() { playing.value ? stopPlay() : startPlay(); }
function startPlay() {
  playing.value = true;
  playTimer = setInterval(() => {
    if (currentStep.value < totalSteps.value - 1) {
      currentStep.value++;
      updateCharts();
    } else {
      stopPlay();
    }
  }, 1500);
}
function stopPlay() {
  playing.value = false;
  if (playTimer) { clearInterval(playTimer); playTimer = null; }
}

watch(currentStep, updateCharts);
</script>

<style scoped>
.deduction-page {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: #e2e8f0;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 24px;
  border-bottom: 1px solid rgba(148,163,184,0.15);
  background: rgba(15,23,42,0.6);
  backdrop-filter: blur(10px);
}
.header-left { display: flex; align-items: center; gap: 18px; }
.page-title { 
  margin: 0; 
  display: flex; 
  align-items: center; 
  gap: 10px; 
  font-size: 18px; 
  color: #fbbf24;
}
.header-right { display: flex; gap: 10px; }
.page-body {
  flex: 1;
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
  padding: 16px;
  overflow: hidden;
}
.left-config {
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
  padding-right: 4px;
}
.right-visual { min-width: 0; }
.card {
  background: rgba(30,41,59,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 12px;
  padding: 16px;
  backdrop-filter: blur(8px);
}
.card.full-height { height: 100%; display: flex; flex-direction: column; }
.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #fbbf24;
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid #38BDF8;
}
.card-title-with-tabs {
  font-size: 14px;
  font-weight: 600;
  color: #fbbf24;
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 3px solid #3b82f6;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.step-player { display: flex; align-items: center; gap: 8px; }
.step-label { color: #94a3b8; font-size: 12px; min-width: 70px; }
.selected-info {
  margin-top: 10px;
  padding: 10px;
  background: rgba(59,130,246,0.08);
  border-radius: 6px;
  border-left: 3px solid #3b82f6;
  font-size: 12px;
  line-height: 1.8;
}
.empty-hint {
  padding: 30px 10px;
  text-align: center;
  color: #64748b;
  font-size: 12px;
}
.stats { display: grid; grid-template-columns: repeat(3,1fr); gap: 8px; }
.stat-item { text-align: center; padding: 10px 4px; background: rgba(15,23,42,0.5); border-radius: 8px; }
.stat-value { font-size: 20px; font-weight: 700; }
.stat-value.red { color: #ef4444; }
.stat-value.orange { color: #38BDF8; }
.stat-value.blue { color: #38BDF8; }
.stat-label { font-size: 11px; color: #94a3b8; margin-top: 3px; }
.charts-area { flex: 1; display: flex; flex-direction: column; gap: 12px; min-height: 0; }
.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.chart-box { 
  background: rgba(15,23,42,0.4); 
  border-radius: 8px; 
  padding: 10px 12px;
  border: 1px solid rgba(148,163,184,0.1);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.chart-box.full-width { flex: 1.2; }
.chart-title { font-size: 12px; color: #94a3b8; margin-bottom: 6px; font-weight: 500; }
.chart { flex: 1; width: 100%; min-height: 240px; }
.chart.tall { min-height: 280px; }
.empty-visual { flex: 1; display: flex; align-items: center; justify-content: center; opacity: 0.6; }
</style>
