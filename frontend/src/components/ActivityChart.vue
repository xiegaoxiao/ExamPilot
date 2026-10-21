<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { init, use, type ECharts } from "echarts/core";
import { BarChart } from "echarts/charts";
import {
  AriaComponent,
  GridComponent,
  TooltipComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
use([BarChart, AriaComponent, GridComponent, TooltipComponent, SVGRenderer]);
const props = defineProps<{ rows: { day: string; count: number }[] }>();
const host = ref<HTMLDivElement | null>(null);
let chart: ECharts | undefined;
let observer: ResizeObserver | undefined;
function render() {
  if (!chart || !host.value) return;
  const styles = getComputedStyle(host.value);
  chart.setOption({
    animation: !matchMedia("(prefers-reduced-motion: reduce)").matches,
    aria: { enabled: true },
    grid: { top: 24, bottom: 24, left: 8, right: 8 },
    tooltip: {
      trigger: "axis",
      formatter: "{b}<br/>{c} 次练习",
      confine: true,
    },
    xAxis: {
      type: "category",
      data: props.rows.map((row) => row.day.slice(5).replace("-", "/")),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: styles.getPropertyValue("--color-muted").trim(),
        fontSize: 10,
      },
    },
    yAxis: {
      type: "value",
      show: false,
      min: 0,
      max: Math.max(1, ...props.rows.map((row) => row.count)),
    },
    series: [
      {
        name: "实际作答次数",
        type: "bar",
        data: props.rows.map((row) => row.count),
        barMaxWidth: 28,
        showBackground: true,
        backgroundStyle: {
          color: styles.getPropertyValue("--color-canvas").trim(),
          borderRadius: 5,
        },
        itemStyle: {
          color: styles.getPropertyValue("--color-action").trim(),
          borderRadius: 5,
        },
        label: {
          show: true,
          position: "top",
          color: styles.getPropertyValue("--color-muted").trim(),
          fontSize: 10,
        },
      },
    ],
  });
}
onMounted(() => {
  if (!host.value) return;
  chart = init(host.value, undefined, { renderer: "svg" });
  render();
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(host.value);
});
watch(() => props.rows, render, { deep: true });
onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>
<template>
  <div
    ref="host"
    class="activity-chart"
    role="img"
    aria-label="最近七天实际作答次数"
  ></div>
</template>
