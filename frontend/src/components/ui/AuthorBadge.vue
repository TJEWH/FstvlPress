<template>
  <span
    v-if="name"
    ref="badgeEl"
    class="author-badge"
    :class="{ 'on-dark': onDark }"
    :title="name"
    role="button"
    tabindex="0"
    @mouseenter="showTooltip"
    @mouseleave="hideTooltip"
    @focus="showTooltip"
    @blur="hideTooltip"
    @keydown.escape.stop="hideTooltip"
    @click.stop="toggle"
  >
    <font-awesome-icon :icon="faCircleUser" class="author-icon" />

    <Teleport to="body">
      <div
        v-if="visible"
        class="author-badge-tooltip"
        :style="tooltipStyle"
      >
        <span class="author-badge-tooltip-name">{{ name }}</span>
        <span v-if="formattedTime" class="author-badge-tooltip-time">{{ formattedTime }}</span>
      </div>
    </Teleport>
  </span>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { faCircleUser } from "@fortawesome/free-solid-svg-icons";
import { parseRevisionTimestamp, getServerTimezone } from "../../utils/revisionTime.js";

const props = defineProps({
  name: { type: String, default: null },
  timestamp: { type: String, default: null },
  onDark: { type: Boolean, default: false },
});

const badgeEl = ref(null);
const visible = ref(false);
const tooltipStyle = ref({});
let timer = null;

const formattedTime = computed(() => {
  if (!props.timestamp) return null;
  try {
    const d = parseRevisionTimestamp(props.timestamp);
    if (!d) return null;
    const formatted = d.toLocaleString("de-DE", {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: getServerTimezone(),
    });
    const timezoneLabel = getServerTimezone().split('/').pop() || getServerTimezone();
    return `${formatted} ${timezoneLabel}`;
  } catch { return null; }
});

function positionTooltip() {
  if (!badgeEl.value) return;
  const rect = badgeEl.value.getBoundingClientRect();
  tooltipStyle.value = {
    position: 'fixed',
    left: `${rect.left + rect.width / 2}px`,
    top: `${rect.top - 6}px`,
    transform: 'translate(-50%, -100%)',
    zIndex: '9999',
  };
}

function toggle() {
  clearTimeout(timer);
  if (visible.value) {
    visible.value = false;
    return;
  }
  positionTooltip();
  visible.value = true;
  timer = setTimeout(() => { visible.value = false; }, 2000);
}

function showTooltip() {
  clearTimeout(timer);
  positionTooltip();
  visible.value = true;
}

function hideTooltip() {
  clearTimeout(timer);
  visible.value = false;
}

function close() { hideTooltip(); }

onMounted(() => {
  document.addEventListener('click', close);
  window.addEventListener('scroll', close, true);
});
onBeforeUnmount(() => {
  document.removeEventListener('click', close);
  window.removeEventListener('scroll', close, true);
  clearTimeout(timer);
});
</script>

<style>
.author-badge-tooltip {
  background: #1e293b;
  color: #f8fafc;
  font-size: 11px;
  font-weight: 600;
  padding: 5px 10px;
  border-radius: 6px;
  white-space: nowrap;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  animation: authorBadgeTipIn 120ms ease;
}

.author-badge-tooltip-name { line-height: 1.3; }

.author-badge-tooltip-time {
  font-weight: 400;
  opacity: 0.7;
  font-size: 10px;
  line-height: 1.3;
}

@keyframes authorBadgeTipIn {
  from { opacity: 0; transform: translate(-50%, calc(-100% + 2px)); }
  to   { opacity: 1; transform: translate(-50%, -100%); }
}
</style>

<style scoped>
.author-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(79, 70, 229, 0.1);
  color: rgba(79, 70, 229, 0.7);
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s ease, color 0.15s ease;
}

.author-badge:hover {
  background: rgba(79, 70, 229, 0.18);
  color: rgba(79, 70, 229, 0.9);
}

.author-badge.on-dark {
  background: rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.7);
}

.author-badge.on-dark:hover {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}

.author-icon {
  font-size: 14px;
}
</style>
