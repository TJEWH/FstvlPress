/* Personal bikeshadding component... ^^ */

<template>
  <SectionBase :section-key="effectiveKey" :section-data="section" :class="sectionClasses" :style="sectionStyle">
    <!-- ====== Minimal Wrapper (Just Video) ====== -->
    <div v-if="hasVideoEmbed && effectiveWrapper === 'minimal'" class="minimal-wrap">
      <div class="minimal-video">
        <iframe
            :src="youtubeEmbedUrl"
            title="Video"
            frameborder="0"
            allow="accelerometer; autoplay; fullscreen; picture-in-picture; encrypted-media"
            referrerpolicy="strict-origin-when-cross-origin"
            loading="lazy"
            allowfullscreen
        ></iframe>
      </div>
    </div>

    <!-- ====== Curtains Wrapper (Theater Curtain) ====== -->
    <div v-if="hasVideoEmbed && effectiveWrapper === 'curtains'" class="curtains-wrap">
      <div
        ref="theaterRef"
        class="theater"
        :class="{ 'theater--open': curtainsOpen, 'theater--dismissed': curtainsDismissed }"
        @mouseenter="onTheaterEnter"
        @mouseleave="onTheaterLeave"
        @click="onTheaterClick"
      >
        <div class="theater-screen">
          <iframe
              :id="ytIframeId"
              :src="youtubeEmbedUrl"
              title="Video"
              frameborder="0"
              allow="accelerometer; autoplay; fullscreen; picture-in-picture; encrypted-media"
              referrerpolicy="strict-origin-when-cross-origin"
              loading="lazy"
              allowfullscreen
              @load="initYTPlayer"
          ></iframe>
        </div>
        <div v-if="!curtainsDismissed" class="theater-click-zone" @click.stop="onTheaterClick"></div>
        <div class="curtain curtain-left"></div>
        <div class="curtain curtain-right"></div>
        <div class="pelmet"></div>
      </div>
    </div>

    <!-- ====== TV Wrapper ====== -->
    <div v-if="hasVideoEmbed && effectiveWrapper === 'tv'" class="tv-wrap">
      <div class="tv" :class="{ on: isOn }" :style="tvStyleVars">
        <div class="antenna-container">
          <div 
            class="antenna" 
            :class="{ animating: antennaAnimating }"
            :style="`--antenna-deg: ${antennaDeg}deg`"
          ></div>
        </div>

        <div class="television-container">
          <div class="television">
            <div class="television-inner">
              <div class="television-screen-container">
                <div class="television-crt">
                  <div class="television-screen">
                    <div class="off"></div>

                    <div class="video-layer">
                      <iframe
                          class="video"
                          :src="youtubeEmbedUrl"
                          title="Video"
                          frameborder="0"
                          allow="accelerometer; autoplay; fullscreen; picture-in-picture; encrypted-media"
                          referrerpolicy="strict-origin-when-cross-origin"
                          loading="lazy"
                          allowfullscreen
                      ></iframe>
                    </div>

                    <div class="noise" :class="{ intense: noiseIntense }"></div>
                  </div>
                </div>
              </div>

              <div class="television-lateral">
                <div class="dial-container">
                  <div
                      class="dial channel-button"
                      :style="{ '--value': channelDeg + 'deg' }"
                      @click="togglePower"
                      title="Channel (click / right click)"
                  >
                  </div>

                  <div
                      class="dial volume-button"
                      :style="{ '--value': volumeDeg + 'deg' }"
                      @click.prevent="rotateDial('volume', 1)"
                      @contextmenu.prevent="rotateDial('volume', -1)"
                      title="Volume (click / right click)"
                  >
                    <div class="selector"></div>
                  </div>
                </div>

                <div class="speaker-container" aria-hidden="true">
                  <div v-for="n in speakerCount" :key="n"></div>
                </div>
              </div>
            </div>
          </div>

          <!-- television-base entfernt -->
          <div class="foot-container" aria-hidden="true">
            <div class="foot left"></div>
            <div class="foot right"></div>
          </div>
        </div>

      </div>
    </div>

    <!-- Admin controls -->
    <template #admin-design-params>
        <div class="admin-bar video-design-panel">
          <label class="ab-row">
            <span class="ab-label">View</span>
            <select class="ab-select video-view-select" :value="currentWrapper" @change="setUnifiedWrapper($event.target.value)">
              <option value="tv">TV</option>
              <option value="curtains">Curtains</option>
              <option value="minimal">Minimal</option>
            </select>
          </label>
        </div>
    </template>
    <template v-if="currentWrapper === 'tv'" #admin-design-colors>
        <div class="admin-bar">
          <div class="ab-row">
            <span class="ab-label">TV Color</span>
            <div class="tv-color-control">
              <VueColorPicker
                :model-value="hexOrDefault(tvColor, '#f2c94c')"
                fallback-color="#f2c94c"
                :preview-style="swatchStyle(resolveTvColor(tvColor, tvColorVariation), { rawColor: tvColor, linkKey: tvColorLink, treatEmptyAsHighContrast: true, baseRefColor: state.design.sectionBackgroundColor || '#ffffff', baseRefKey: 'sectionBackgroundColor', adminConfig: state.adminDesignConfig })"
                :size="28"
                @update:model-value="setTvColor($event)"
              />
              <ColorLinkPicker :model-value="tvColorLink" :options="baseColorOptions" :button-size="24" @link="applyColorLink" />
              <select
                class="variation-select"
                :value="tvColorVariation"
                @change="setTvColorVariation($event.target.value)"
              >
                <option v-for="variation in colorVariationOptions" :key="`video-tv-${variation}`" :value="variation">
                  {{ variation }}%
                </option>
              </select>
              <button v-if="tvColor" class="clear-btn" type="button" title="Clear" @click="setTvColor(null)">&times;</button>
            </div>
          </div>
        </div>
    </template>
    <template #admin-content>
        <div class="admin-bar video-admin-bar">
          <label class="video-source-field">
            <span class="ab-label">Source</span>
            <select
                v-model="draftVideoProvider"
                class="ab-select video-source-select"
                :disabled="isVideoFieldLocked('videoId') || isVideoFieldLocked('videoProvider')"
                :title="(isVideoFieldLocked('videoId') || isVideoFieldLocked('videoProvider')) ? integrationLockedHint : undefined"
                @blur="saveVideoUrl"
            >
              <option v-for="option in videoProviderOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
          <label class="video-url-field">
            <span class="ab-label">Video URL</span>
            <input
                ref="videoInputRef"
                v-model="draftVideoInput"
                class="ab-input video-id-input"
                type="text"
                :placeholder="currentVideoInputPlaceholder"
                :disabled="isVideoFieldLocked('videoId') || isVideoFieldLocked('videoProvider')"
                :title="(isVideoFieldLocked('videoId') || isVideoFieldLocked('videoProvider')) ? integrationLockedHint : undefined"
                @keydown.enter="saveVideoUrl"
                @blur="saveVideoUrl"
            />
          </label>
        </div>
    </template>
  </SectionBase>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted, onBeforeUnmount } from "vue";
import { useStore } from "../../store/store.js";
import {
  buildColorLinkOptions,
  resolveLinkedColor,
  HIGH_CONTRAST_TOKEN,
  resolveHighContrastColorForBackground,
} from "../../utils/colorLinkOptions.js";
import {
  COLOR_VARIATION_OPTIONS,
  DEFAULT_COLOR_VARIATION,
  applyColorVariation,
  normalizeColorVariation,
} from "../../utils/colorVariations.js";
import { isSectionHiddenInPublicBecauseEmptyList } from "../../utils/sectionVisibilityRules.js";
import { getBaseSectionSwatchStyle } from "./_baseSectionSwatchStyle.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";

import SectionBase from "./_BaseSection.vue";
import ColorLinkPicker from "../ui/color/ColorLinkPicker.vue";
import VueColorPicker from "../ui/color/VueColorPicker.vue";

const props = defineProps({
  sectionKey: { type: String, default: 'video' },
  sectionData: { type: Object, default: null }
});

const { state, updateSection, t } = useStore();
const integrationLockedHint = "Managed by integration import.";

// Effective key for this section instance
const effectiveKey = computed(() => props.sectionKey);

// Get section data from props or sectionsData
const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});

function isVideoFieldLocked(path, options = {}) {
  return state.isAdmin && isSectionIntegrationFieldLocked(section.value, path, options);
}

// Screen size detection for responsive wrapper and speaker count
const screenWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1024);

function updateScreenWidth() {
  screenWidth.value = window.innerWidth;
}

const DEFAULT_VIDEO_PROVIDER = "youtube";
const videoProviderOptions = Object.freeze([
  { value: "youtube", label: "YouTube" },
  { value: "vimeo", label: "Vimeo" },
]);

function normalizeVideoProvider(provider) {
  const normalized = String(provider || "").trim().toLowerCase();
  return normalized === "vimeo" ? "vimeo" : DEFAULT_VIDEO_PROVIDER;
}

// Current video ID and provider
const currentVideoId = computed(() => String(section.value?.videoId || "").trim());
const hasVideoEmbed = computed(() => currentVideoId.value.length > 0);
const currentVideoProvider = computed(() => normalizeVideoProvider(section.value?.videoProvider));
const draftVideoProvider = ref(DEFAULT_VIDEO_PROVIDER);
const currentVideoInputPlaceholder = computed(() => {
  if (normalizeVideoProvider(draftVideoProvider.value) === "vimeo") {
    return currentVideoId.value ? `https://vimeo.com/${currentVideoId.value}` : "https://vimeo.com/123456789";
  }
  return currentVideoId.value ? `https://youtu.be/${currentVideoId.value}` : "https://youtu.be/VIDEO_ID";
});

const currentWrapper = computed(() => section.value?.wrapper || "tv");
const tvColor = computed(() => section.value?.tvColor ?? null);
const tvColorLink = computed(() => section.value?.tvColorLink ?? null);
const tvColorVariation = computed(() => normalizeColorVariation(section.value?.tvColorVariation));
const colorVariationOptions = COLOR_VARIATION_OPTIONS;
const baseColorOptions = computed(() =>
  buildColorLinkOptions(state.design, {
    parameterConfigs: state.adminDesignConfig?.parameters,
  })
);

// Get the current device type based on simulation or real screen
const currentDeviceType = computed(() => {
  const sim = state.simulatedViewport;
  if (sim === 'mobile') return 'mobile';
  if (sim === 'tablet') return 'tablet';
  if (sim === 'desktop') return 'desktop';
  
  // No simulation - use real screen width
  if (screenWidth.value < 768) return 'mobile';
  if (screenWidth.value < 1024) return 'tablet';
  return 'desktop';
});

const effectiveWrapper = computed(() => {
  return currentWrapper.value;
});

const sectionClasses = computed(() => [
  effectiveWrapper.value === 'tv' ? 'tv-section' : '',
  isAdminPublicHidden.value ? 'video-section--admin-hidden' : '',
]);

const sectionStyle = computed(() => {
  if (effectiveWrapper.value !== 'curtains') return {};
  const base = { transition: 'background-color 0.8s ease, box-shadow 0.8s ease' };
  if (curtainsDismissed.value) {
    return { ...base, backgroundColor: '#0a0a0a', boxShadow: 'none' };
  }
  return base;
});

const tvStyleVars = computed(() => {
  return { "--tv-body": resolveTvColor(tvColor.value, tvColorVariation.value) };
});

const isAdminPublicHidden = computed(() =>
  state.isAdmin
  && !state.previewMode
  && isSectionHiddenInPublicBecauseEmptyList(effectiveKey.value, state, section.value)
);

function hexOrDefault(val, fallback) {
  if (val && /^#[0-9a-fA-F]{6}$/.test(val)) return val;
  return fallback;
}

function swatchStyle(previewColor, options = {}) {
  return getBaseSectionSwatchStyle(state.design, previewColor, options);
}

function contrastColor(bgHex, backgroundBaseKey = null) {
  return resolveHighContrastColorForBackground(
    state.design,
    state.adminDesignConfig,
    {
      backgroundColor: bgHex,
      backgroundBaseKey,
    }
  );
}

function resolveTvColor(value, variation = DEFAULT_COLOR_VARIATION) {
  let resolved;
  if (!value || value === HIGH_CONTRAST_TOKEN) {
    const sectionBg = state.design.sectionBackgroundColor || "#ffffff";
    resolved = contrastColor(sectionBg, "sectionBackgroundColor");
  } else {
    resolved = value;
  }
  return applyColorVariation(resolved, variation);
}

function resolveBaseColor(linkKey) {
  return resolveLinkedColor(state.design, linkKey, state.adminDesignConfig?.parameters);
}

function applyColorLink(baseKey) {
  const resolved = resolveBaseColor(baseKey);
  updateSection(effectiveKey.value, { tvColor: resolved, tvColorLink: baseKey });
}

function setTvColor(val) {
  updateSection(effectiveKey.value, { tvColor: val, tvColorLink: null });
}

function setTvColorVariation(value) {
  const normalized = normalizeColorVariation(value);
  updateSection(effectiveKey.value, {
    tvColorVariation: normalized === DEFAULT_COLOR_VARIATION ? null : normalized,
  });
}

function setUnifiedWrapper(wrapper) {
  curtainsDismissed.value = false;
  curtainsOpen.value = false;
  updateSection(effectiveKey.value, { wrapper, deviceWrappers: {} });
}

// Build embed URL from stored video ID and provider
const youtubeEmbedUrl = computed(() => {
  const videoId = currentVideoId.value;
  if (!videoId) return "";
  if (currentVideoProvider.value === "vimeo") {
    return `https://player.vimeo.com/video/${videoId}?title=0&byline=0&portrait=0`;
  }
  return `https://www.youtube-nocookie.com/embed/${videoId}?rel=0&modestbranding=1&playsinline=1&enablejsapi=1`;
});

// Extract provider + video ID from YouTube and Vimeo URL formats.
// Full URLs imply their own provider; bare IDs use the selected source dropdown.
function extractVideoInfo(input, selectedProvider = DEFAULT_VIDEO_PROVIDER) {
  if (!input) return null;

  const trimmed = input.trim();
  const provider = normalizeVideoProvider(selectedProvider);

  // youtu.be/VIDEO_ID
  const shortMatch = trimmed.match(/youtu\.be\/([a-zA-Z0-9_-]{11})/);
  if (shortMatch) {
    return { provider: "youtube", videoId: shortMatch[1] };
  }

  // youtube.com/watch?v=VIDEO_ID or youtube.com/embed/VIDEO_ID
  const watchMatch = trimmed.match(/[?&]v=([a-zA-Z0-9_-]{11})/);
  if (watchMatch) {
    return { provider: "youtube", videoId: watchMatch[1] };
  }

  // youtube.com/embed/VIDEO_ID or youtube-nocookie.com/embed/VIDEO_ID
  const embedMatch = trimmed.match(/\/embed\/([a-zA-Z0-9_-]{11})/);
  if (embedMatch) {
    return { provider: "youtube", videoId: embedMatch[1] };
  }

  // vimeo.com/VIDEO_ID, player.vimeo.com/video/VIDEO_ID, or channel/group variants
  const vimeoMatch = trimmed.match(/vimeo\.com\/(?:.*\/)?(\d+)(?:$|[?#])/i);
  if (vimeoMatch) {
    return { provider: "vimeo", videoId: vimeoMatch[1] };
  }

  if (provider === "vimeo" && /^\d+$/.test(trimmed)) {
    return { provider, videoId: trimmed };
  }

  if (provider === "youtube" && /^[a-zA-Z0-9_-]{11}$/.test(trimmed)) {
    return { provider, videoId: trimmed };
  }

  return null;
}

// Video URL editing
const draftVideoInput = ref("");
const videoInputRef = ref(null);

// Keep draft in sync with stored video ID
watch(() => section.value?.videoId, (id) => {
  draftVideoInput.value = id || "";
}, { immediate: true });

watch(() => section.value?.videoProvider, (provider) => {
  draftVideoProvider.value = normalizeVideoProvider(provider);
}, { immediate: true });

watch(() => [state.design.primaryColor, state.design.secondaryColor, state.design.backgroundColor, state.design.accentColor, state.design.sectionBackgroundColor, state.design.highContrastDark, state.design.highContrastLight], () => {
  const link = tvColorLink.value;
  if (!link) return;
  const resolved = resolveBaseColor(link);
  if (resolved !== null) {
    updateSection(effectiveKey.value, { tvColor: resolved });
  }
});

function saveVideoUrl() {
  if (isVideoFieldLocked("videoId") || isVideoFieldLocked("videoProvider")) return;
  const selectedProvider = normalizeVideoProvider(draftVideoProvider.value);
  const rawInput = String(draftVideoInput.value || "").trim();
  if (!rawInput) {
    if (section.value?.videoId || currentVideoProvider.value !== selectedProvider) {
      updateSection(effectiveKey.value, {
        videoId: "",
        videoProvider: selectedProvider,
      });
    }
    return;
  }

  const videoInfo = extractVideoInfo(draftVideoInput.value, selectedProvider);
  if (!videoInfo) return;
  draftVideoProvider.value = videoInfo.provider;
  if (
    videoInfo.videoId !== section.value?.videoId
    || videoInfo.provider !== currentVideoProvider.value
  ) {
    updateSection(effectiveKey.value, {
      videoId: videoInfo.videoId,
      videoProvider: videoInfo.provider,
    });
  }
}

// Theater curtain (minimal wrapper)
const theaterRef = ref(null);
const curtainsOpen = ref(false);
const curtainsDismissed = ref(false);
let curtainCloseTimer = null;

function onTheaterEnter() {
  if (curtainsDismissed.value) return;
  clearTimeout(curtainCloseTimer);
  curtainsOpen.value = true;
}

function onTheaterLeave(e) {
  if (curtainsDismissed.value) return;
  clearTimeout(curtainCloseTimer);
  if (!e.relatedTarget) return;
  curtainCloseTimer = setTimeout(() => {
    curtainsOpen.value = false;
  }, 600);
}

function onTheaterClick() {
  if (!curtainsDismissed.value) {
    curtainsDismissed.value = true;
    curtainsOpen.value = true;
    try { ytPlayer?.playVideo(); } catch {}
  }
}

// YouTube IFrame API — detect play/pause/end
const ytIframeId = computed(() => `video-yt-${effectiveKey.value}`);
let ytPlayer = null;

function loadYTApi() {
  return new Promise((resolve) => {
    if (window.YT?.Player) { resolve(); return; }
    const prev = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => { prev?.(); resolve(); };
    if (!document.querySelector('script[src*="youtube.com/iframe_api"]')) {
      const s = document.createElement('script');
      s.src = 'https://www.youtube.com/iframe_api';
      document.head.appendChild(s);
    }
  });
}

async function initYTPlayer() {
  if (effectiveWrapper.value !== 'curtains') return;
  if (currentVideoProvider.value !== "youtube") return;
  await loadYTApi();
  const el = document.getElementById(ytIframeId.value);
  if (!el) return;
  ytPlayer = null;
  try {
    ytPlayer = new window.YT.Player(ytIframeId.value, {
      events: {
        onStateChange(e) {
          if (e.data === 1) {
            curtainsDismissed.value = true;
            curtainsOpen.value = true;
          } else if (e.data === 0 || e.data === 2) {
            curtainsDismissed.value = false;
            curtainsOpen.value = false;
          }
        }
      }
    });
  } catch (err) {
    console.warn('YT player init failed:', err);
  }
}

onMounted(() => {
  updateScreenWidth();
  window.addEventListener('resize', updateScreenWidth);
});

onBeforeUnmount(() => {
  ytPlayer = null;
  clearTimeout(curtainCloseTimer);
  window.removeEventListener('resize', updateScreenWidth);
});

// Speaker count based on current device: mobile 24, tablet 36, desktop 48
const speakerCount = computed(() => {
  const device = currentDeviceType.value;
  if (device === 'mobile') return 24;
  if (device === 'tablet') return 36;
  return 48;
});

const isOn = ref(true);
const channelDeg = ref(0);
const volumeDeg = ref(0);

// Antenna state
const antennaDeg = ref(16); // Initial position
const antennaAnimating = ref(false);
const noiseIntense = ref(false);

const ANTENNA_MIN_DEG = 5;
const ANTENNA_MAX_DEG = 60;
const ANIMATION_DURATION = 400; // ms

function randomizeAntenna() {
  if (antennaAnimating.value) return;
  
  antennaAnimating.value = true;
  noiseIntense.value = true;
  
  // Random position within range
  antennaDeg.value = ANTENNA_MIN_DEG + Math.random() * (ANTENNA_MAX_DEG - ANTENNA_MIN_DEG);
  
  setTimeout(() => {
    antennaAnimating.value = false;
    noiseIntense.value = false;
  }, ANIMATION_DURATION);
}
function togglePower() {
  isOn.value = !isOn.value;
}
function rotateDial(which, dir = 1) {
  const step = 30 * dir;
  if (which === "channel") channelDeg.value += step;
  if (which === "volume") {
    volumeDeg.value += step;
    randomizeAntenna();
  }
}
</script>

<style scoped>
.video-section--admin-hidden {
  filter: grayscale(0.85) saturate(0.35);
}

.video-section--admin-hidden :deep(.section-header),
.video-section--admin-hidden :deep(.section-description),
.video-section--admin-hidden :deep(.section-content),
.video-section--admin-hidden :deep(.section-cta-actions) {
  opacity: 0.38;
}

.tv-section .section-header {
  justify-content: center !important;
}

.tv-wrap {
  display: grid;
  place-items: center;
  margin: calc(var(--section-padding) * -2.5) 0 calc(var(--section-padding) * -1);
}

/* Wider + yellow TV */
.tv {
  --tv-body: var(--section-background-color, #f2c94c);
  --tv-body-dark: color-mix(in srgb, var(--tv-body) 80%, black);
  --antenna-height: 85px;

  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: calc(var(--antenna-height) / 2);
}

/* Antenna */
.antenna-container {
  width: 80%;
  height: var(--antenna-height);
  display: flex;
  pointer-events: none;
  flex-direction: column;
  justify-content: flex-end;
  z-index: 0;
}
.antenna {
  width: 100%;
  height: 4px;
  background: linear-gradient(to top, #444 10%, #999 25% 40%, #444 70%, #2224 100%);
  transform-origin: 100% 50%;
  transform: rotate(var(--antenna-deg, 16deg)) translateY(3px);
  display: flex;
  align-items: center;
  pointer-events: none;
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.antenna.animating {
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.antenna::before {
  content: "";
  width: 8px;
  height: 10px;
  background: linear-gradient(to top, #444 10%, #999 25% 40%, #444 70%, #2224 1300%);
  border-radius: 24% 53% 53% 24% / 36% 40% 40% 36%;
  border: 1px solid #444;
  border-left: 0;
  border-bottom: 0;
  transform: translateY(0px);
}

.television-container { display: flex; flex-direction: column; align-items: center; z-index: 1; }

.television {
  border-radius: 20px;
  background: linear-gradient(var(--tv-body), var(--tv-body-dark));
  box-shadow: 0 16px 40px rgba(15,23,42,0.18);
  display: flex;
  justify-content: center;
  align-items: center;
}

.television-inner {
  width: 100%;
  position: relative;
  display: grid;
  grid-template-columns: 3.6fr 1fr;
  align-content: center;
  gap: 20px;
  border-radius: 20px;
  margin: 20px;
}
/*  background: linear-gradient(to bottom, rgba(255,255,255,0.10), rgba(0,0,0,0.10)); */

/* Screen */
.television-screen-container {
  height: 100%;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.12) inset;
  border-radius: 12px;
}

.television-crt {
  width: 100%;
  height: 100%;
  background: #0b0f16;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
  box-shadow: 0 0 0 2px rgba(255,255,255,0.06) inset;
}

.television-screen {
  width: 100%;
  height: 100%;
  overflow: hidden;
  position: relative;
}

/* Video: klickbar */
.video-layer {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: grid;
  place-items: center;
}
.video {
  width: 100%;
  height: 100%;
  border: 0;
}

/* Noise: blockt nie */
.noise {
  position: absolute;
  inset: 0;
  z-index: 3;
  pointer-events: none;
  background:
      linear-gradient(to bottom, transparent, rgba(255,255,255,0.10), rgba(255,255,255,0.04), rgba(0,0,0,0.20), transparent),
      repeating-linear-gradient(transparent 0 2px, rgba(0,0,0,0.12) 2px 4px);
  animation: moveBand 8s linear infinite;
  opacity: 0.62;
  transition: opacity 0.15s ease-out;
}

/* Intense noise during antenna adjustment */
.noise.intense {
  opacity: 1;
  background:
      linear-gradient(to bottom, transparent, rgba(255,255,255,0.25), rgba(255,255,255,0.15), rgba(0,0,0,0.35), transparent),
      repeating-linear-gradient(transparent 0 1px, rgba(255,255,255,0.15) 1px 2px, transparent 2px 3px, rgba(0,0,0,0.2) 3px 4px);
  animation: moveBand 0.3s linear infinite, flicker 0.1s steps(2) infinite;
}

@keyframes flicker {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.85; }
}

/* Off overlay blockt nur bei OFF */
.off {
  position: absolute;
  inset: 0;
  z-index: 4;
  background: radial-gradient(#111827, #0b0f16, #05070b);
  opacity: 1;
  transition: opacity 0.5s ease;
  pointer-events: auto;
}
.tv.on .off {
  opacity: 0;
  pointer-events: none;
}

/* Lateral */
.television-lateral {
  display: grid;
  gap: 12px;
}

.dial-container {
  border-radius: 12px;
  background: rgba(0,0,0,0.10);
  box-shadow: 0 10px 18px rgba(0,0,0,0.15) inset;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
  align-items: center;
  padding: 12px 0;
}

.dial {
  width: 48px;
  height: 48px;
  border: 2px solid rgba(255,255,255,0.14);
  border-radius: 50%;
  position: relative;
  user-select: none;
  cursor: pointer;
  box-shadow: -4px 2px 10px rgba(0,0,0,0.35);
}

.channel-button { background: #0b0f16; }
.volume-button { background: #e9edf5; }


.selector {
  position: absolute;
  top: 50%;
  left: 3%;
  width: 100%;
  height: 7px;
  border-radius: 999px;
  background: black;
  transform: translate(-2%, -50%) rotate(calc(var(--value) - 90deg));
  transition: transform 0.25s linear;
}

/* Speaker holes */
.speaker-container {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 2px;
}
.speaker-container > div {
  width: 10px;
  height: 10px;
  background: radial-gradient(#000, #222);
  border-radius: 50%;
  border-bottom: 1px solid rgba(255,255,255,0.12);
}

/* Buttons */
.buttons {
  position: absolute;
  bottom: 10px;
  right: 26px;
  width: 68px;
  display: flex;
  justify-content: space-between;
}

.button-container {
  width: 22px;
  height: 22px;
  background: rgba(0,0,0,0.10);
  border: 1px solid rgba(0,0,0,0.12);
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
}

.button {
  width: 12px;
  height: 12px;
  border: 0;
  border-radius: 50%;
  background: #cbd5e1;
  cursor: pointer;
  box-shadow: 0 2px 0 rgba(0,0,0,0.25);
}
.button.power { background: var(--accent); }
.button:active { transform: translateY(1px); }

/* Feet only */
.foot-container { width: 70%; display: flex; justify-content: space-between; display: none}
.foot { width: 20px; height: 10px; background: var(--tv-body-dark); }
.foot.left { box-shadow: 4px 0 rgba(0,0,0,0.22); }
.foot.right { box-shadow: -4px 0 rgba(0,0,0,0.22); }

@keyframes moveBand {
  0% { background-position-y: 0, 0; }
  100% { background-position-y: -221px, -150px; }
}

/* ---- Admin bar ---- */
.admin-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  position: relative;
  z-index: 5;
}
.video-admin-bar {
  align-items: flex-end;
}
.video-design-panel {
  margin-bottom: 0;
}
.ab-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ab-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--muted, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  flex-shrink: 0;
}
.ab-input {
  max-width: 100%;
  height: 34px;
  box-sizing: border-box;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 16px;
  border-radius: 8px;
  border: 1px solid var(--border, #e2e8f0);
  background: #fff;
  color: var(--text, #0b1220);
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.ab-input:focus {
  border-color: var(--accent, #4f46e5);
  box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.15);
}
.ab-input::placeholder {
  color: var(--muted, #94a3b8);
}
.ab-select {
  max-width: 100%;
  height: 34px;
  box-sizing: border-box;
  padding: 7px 28px 7px 12px;
  font-size: 12px;
  line-height: 16px;
  border-radius: 8px;
  border: 1px solid var(--border, #e2e8f0);
  background: #fff;
  color: var(--text, #0b1220);
  outline: none;
}
.ab-select:focus {
  border-color: var(--accent, #4f46e5);
  box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.15);
}
.video-view-select {
  min-width: 130px;
}
.video-source-field,
.video-url-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.video-url-field {
  flex: 1 1 260px;
  min-width: 180px;
}
.video-source-select {
  min-width: 118px;
}
.video-id-input {
  min-width: 100%;
}
/* Device style controls */
.device-style-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.device-style-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: var(--surface-2, #f8fafc);
  border-radius: 6px;
  border: 1px solid var(--border, #e2e8f0);
}

.device-icon {
  font-size: 14px;
  line-height: 1;
}

.device-style-select {
  padding: 2px 4px;
  border-radius: 4px;
  border: 1px solid transparent;
  background: #fff;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  min-width: 70px;
}

.device-style-select:hover {
  border-color: var(--border, #e2e8f0);
}

.device-style-select:focus {
  outline: none;
  border-color: var(--accent, #4f46e5);
}

.tv-color-control {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
}

.variation-select {
  min-width: 68px;
  padding: 4px 6px;
  border-radius: 8px;
  border: 1px solid var(--border, rgba(15,23,42,0.14));
  background: #fff;
  font-size: 12px;
}

.color-swatch {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 2px solid var(--border, rgba(15,23,42,0.14));
  cursor: pointer;
  flex-shrink: 0;
}

.color-input-hidden {
  position: absolute;
  width: 0;
  height: 0;
  overflow: hidden;
  opacity: 0;
  pointer-events: none;
}

@media (max-width: 480px) {
  .device-style-toggles {
    flex-direction: column;
    gap: 6px;
  }
  .device-style-row {
    justify-content: space-between;
  }
}

/* ---- Minimal wrapper (Just Video) ---- */
.minimal-wrap {
  margin-top: 14px;
}

.minimal-video {
  position: relative;
  width: 100%;
  padding-bottom: 56.25%;
  overflow: hidden;
  border-radius: 8px;
  background: #000;
}

.minimal-video iframe {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 0;
}

/* ---- Curtains wrapper (Theater Curtain) ---- */
.curtains-wrap {
  margin-top: 14px;
}

.theater {
  position: relative;
  width: 100%;
  padding-bottom: 56.25%;
  overflow: hidden;
  background: #0a0a0a;
  border-radius: 15px;
}

.theater-screen {
  position: absolute;
  inset: 0;
  z-index: 1;
}
.theater-screen iframe {
  width: 100%;
  height: 100%;
  border: 0;
}

.theater-click-zone {
  position: absolute;
  inset: 0;
  z-index: 2;
  cursor: pointer;
}

.curtain {
  position: absolute;
  top: 0;
  width: 50%;
  height: 100%;
  z-index: 3;
  transition: width 0.3s cubic-bezier(0.7, 0, 0.3, 1), opacity 0.35s ease-out;
  pointer-events: none;
  border-bottom: 8px solid var(--accent, firebrick);
  opacity: 1;
}

.curtain-left {
  left: 0;
  background: linear-gradient(-85deg, var(--accent, firebrick), black);
}
.curtain-right {
  right: 0;
  background: linear-gradient(85deg, var(--accent, firebrick), black);
}

.curtain-left, .curtain-right { background-size: 16.67% 100%; }

/* Hover peek */
.theater--open .curtain {
  width: 50px;
}
@media (max-width: 640px) {
  .theater--open .curtain {
    width: 25px;
  }
}

/* Click dismiss — fade out completely */
.theater--dismissed .curtain {
  width: 0;
  opacity: 0;
  border-bottom-color: transparent;
  transition: width 0.4s cubic-bezier(0.7, 0, 0.3, 1),
              opacity 0.5s ease-out,
              border-bottom-color 0.25s ease;
}
.theater--dismissed .pelmet {
  opacity: 0;
  transition: opacity 0.1s ease-out;
}

.pelmet {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 10px;
  background: #000;
  z-index: 5;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
  transition: opacity 0.4s ease;
}

</style>
