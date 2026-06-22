<template>
  <div class="not-found">
    <div class="not-found-content">
      <div class="not-found-code">{{ resolvedStatusCode }}</div>
      <h1 class="not-found-title">{{ title }}</h1>
      <p class="not-found-message">{{ message }}</p>
      <div class="not-found-actions">
        <router-link to="/" class="btn">
          {{ homeButtonText }}
        </router-link>
      </div>
    </div>
    <div class="not-found-decoration">
      <div class="decoration-circle decoration-circle-1"></div>
      <div class="decoration-circle decoration-circle-2"></div>
      <div class="decoration-circle decoration-circle-3"></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useStore } from '../store/store.js';

const props = defineProps({
  statusCode: {
    type: Number,
    default: 404,
  },
});

const { state } = useStore();

const resolvedStatusCode = computed(() => {
  return Number(props.statusCode) === 410 ? 410 : 404;
});

const isGone = computed(() => resolvedStatusCode.value === 410);

const title = computed(() => {
  if (isGone.value) {
    return state.lang === 'de' ? 'Seite entfernt' : 'Page Gone';
  }
  return state.lang === 'de' ? 'Seite nicht gefunden' : 'Page Not Found';
});

const message = computed(() => {
  if (isGone.value) {
    return state.lang === 'de'
      ? 'Diese Seite wurde absichtlich entfernt und ist nicht mehr verfuegbar (HTTP 410 Gone).'
      : 'This page was intentionally removed and is no longer available (HTTP 410 Gone).';
  }
  return state.lang === 'de' 
    ? 'Die gesuchte Seite existiert nicht oder ist nicht verfügbar.'
    : 'The page you are looking for does not exist or is not available.';
});

const homeButtonText = computed(() => {
  return state.lang === 'de' ? 'Zur Startseite' : 'Go to Homepage';
});
</script>

<style scoped>
.not-found {
  min-height: 80vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  position: relative;
  overflow: hidden;
}

.not-found-content {
  text-align: center;
  position: relative;
  z-index: 1;
  max-width: 500px;
}

.not-found-code {
  font-size: clamp(100px, 20vw, 180px);
  font-weight: 900;
  line-height: 1;
  background: linear-gradient(135deg, var(--accent, #4f46e5) 0%, red 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  opacity: 0.9;
  margin-bottom: 16px;
  letter-spacing: -0.05em;
}

.not-found-title {
  font-size: clamp(24px, 5vw, 36px);
  font-weight: 800;
  color: var(--heading-color, var(--text, #0f172a));
  margin: 0 0 12px;
  line-height: 1.2;
}

.not-found-message {
  font-size: clamp(14px, 2.5vw, 18px);
  color: var(--paragraph-color, var(--muted, #64748b));
  margin: 0 0 32px;
  line-height: 1.6;
}

.not-found-actions {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
}

.not-found-actions .btn {
  padding: 14px 32px;
  font-size: 16px;
  font-weight: 600;
}

/* Decorative background circles */
.not-found-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.decoration-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.08;
  overflow: hidden;
  clip-path: circle(50% at 50% 50%);
  backface-visibility: hidden;
  transform: translate3d(0, 0, 0);
}

.decoration-circle-1 {
  width: 400px;
  height: 400px;
  background: var(--accent, #4f46e5);
  top: -100px;
  right: -100px;
  animation: float 20s ease-in-out infinite;
}

.decoration-circle-2 {
  width: 300px;
  height: 300px;
  background: var(--primary-color, #6366f1);
  bottom: -50px;
  left: -50px;
  animation: float 25s ease-in-out infinite reverse;
}

.decoration-circle-3 {
  width: 200px;
  height: 200px;
  background: var(--secondary-color, #8b5cf6);
  top: 50%;
  left: 10%;
  animation: float 15s ease-in-out infinite;
}

@keyframes float {
  0%, 100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  33% {
    transform: translate3d(20px, -20px, 0) scale(1.05);
  }
  66% {
    transform: translate3d(-10px, 10px, 0) scale(0.95);
  }
}

</style>
