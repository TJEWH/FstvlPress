<template>
  <aside
    class="admin-sticky-sidebar"
    :class="[
      `admin-sticky-sidebar--collapse-${collapse}`,
      { 'admin-sticky-sidebar--bare': bare },
    ]"
    :style="sidebarStyle"
    :aria-label="resolvedAriaLabel"
  >
    <template v-if="bare">
      <slot />
    </template>

    <div v-else class="admin-sticky-sidebar__window">
      <div v-if="hasHeader" class="admin-sticky-sidebar__header">
        <slot name="header">
          <h3 v-if="title">{{ title }}</h3>
          <span v-if="hasCountLabel" class="admin-sticky-sidebar__count">{{ countLabel }}</span>
        </slot>
      </div>

      <p v-if="hint" class="admin-sticky-sidebar__hint">{{ hint }}</p>

      <div class="admin-sticky-sidebar__body">
        <slot />
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, useSlots } from "vue";

const props = defineProps({
  title: {
    type: String,
    default: "",
  },
  countLabel: {
    type: [String, Number],
    default: "",
  },
  hint: {
    type: String,
    default: "",
  },
  ariaLabel: {
    type: String,
    default: "",
  },
  top: {
    type: String,
    default: "72px",
  },
  maxHeight: {
    type: String,
    default: "calc(100vh - 104px)",
  },
  bare: {
    type: Boolean,
    default: false,
  },
  collapse: {
    type: String,
    default: "standard",
    validator: (value) => ["standard", "wide", "never"].includes(value),
  },
});

const slots = useSlots();

const hasCountLabel = computed(() => props.countLabel !== "" && props.countLabel !== null && props.countLabel !== undefined);
const hasHeader = computed(() => Boolean(slots.header || props.title || hasCountLabel.value));
const resolvedAriaLabel = computed(() => props.ariaLabel || props.title || undefined);
const sidebarStyle = computed(() => ({
  "--admin-sticky-sidebar-top": props.top,
  "--admin-sticky-sidebar-max-height": props.maxHeight,
}));
</script>

<style scoped>
.admin-sticky-sidebar {
  position: sticky;
  top: var(--admin-sticky-sidebar-top, 72px);
  align-self: start;
  min-width: 0;
}

.admin-sticky-sidebar--bare {
  display: block;
}

.admin-sticky-sidebar__window {
  max-height: var(--admin-sticky-sidebar-max-height, calc(100vh - 104px));
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}

.admin-sticky-sidebar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid #e2e8f0;
}

.admin-sticky-sidebar__header h3 {
  margin: 0;
  font-size: 16px;
  color: #0f172a;
}

.admin-sticky-sidebar__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.admin-sticky-sidebar__hint {
  margin: 0;
  padding: 10px 14px 0;
  font-size: 13px;
  color: var(--admin-muted, #64748b);
  line-height: 1.45;
}

.admin-sticky-sidebar__body {
  min-height: 0;
  overflow: auto;
  padding: 14px;
}

@media (max-width: 1180px) {
  .admin-sticky-sidebar--collapse-wide {
    position: static;
  }

  .admin-sticky-sidebar--collapse-wide .admin-sticky-sidebar__window {
    max-height: none;
  }
}

@media (max-width: 1024px) {
  .admin-sticky-sidebar--collapse-standard {
    position: static;
  }

  .admin-sticky-sidebar--collapse-standard .admin-sticky-sidebar__window {
    max-height: none;
  }
}
</style>
