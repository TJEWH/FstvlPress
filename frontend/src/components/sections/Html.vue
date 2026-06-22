<template>
  <SectionBase
    :section-key="effectiveKey"
    :section-data="section"
    class="html-section"
    :admin-tabs-visible="state.isAdmin && (!state.previewMode || isTemplateBuilderPage)"
    :show-description="false"
  >
    <div
      v-if="mode === 'embed' && nativeEmbedFrame && nativeEmbedFrame.provider === 'instagram'"
      class="html-preview-wrap html-preview-wrap--embed html-preview-wrap--instagram"
    >
      <div class="instagram-embed-shell" :class="instagramShellClass">
        <iframe
          class="html-preview-frame html-preview-frame--instagram"
          :src="nativeEmbedFrame.src"
          frameborder="0"
          scrolling="no"
          loading="lazy"
          allow="autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share"
          referrerpolicy="strict-origin-when-cross-origin"
          title="Instagram embed"
        ></iframe>
      </div>
    </div>
    <div
      v-else-if="mode === 'embed' && nativeEmbedFrame && nativeEmbedFrame.provider === 'youtube'"
      class="html-preview-wrap html-preview-wrap--embed"
    >
      <div class="youtube-wrap">
        <iframe
          class="html-preview-frame html-preview-frame--youtube"
          :src="nativeEmbedFrame.src"
          title="YouTube video player"
          loading="lazy"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowfullscreen
          referrerpolicy="strict-origin-when-cross-origin"
        ></iframe>
      </div>
    </div>
    <div v-else-if="mode === 'embed' && embedCode.trim()" class="error-message">
      Unsupported or invalid embed code. Use Instagram or YouTube embed code with a valid post/video URL.
    </div>
    <div v-else-if="previewAvailable" class="html-preview-wrap">
      <iframe
        ref="previewIframe"
        class="html-preview-frame"
        :sandbox="iframeSandbox"
        :srcdoc="previewSrcDoc"
        :style="previewFrameStyle"
        loading="eager"
        referrerpolicy="no-referrer"
        title="HTML section preview"
        @load="requestPreviewFrameResize"
      ></iframe>
    </div>
    <div v-else-if="!state.isAdmin" class="empty-content">
      <span class="empty-icon"><font-awesome-icon :icon="faCode" /></span>
      <span>No HTML content configured</span>
    </div>

    <template #admin-content>
      <div class="html-controls">
        <div class="mode-switch">
          <button
            type="button"
            class="mode-btn"
            :class="{ active: mode === 'fetch' }"
            :disabled="isHtmlFieldLocked('mode')"
            @click="setHtmlMode('fetch')"
          >
            Fetch
          </button>
          <button
            type="button"
            class="mode-btn"
            :class="{ active: mode === 'embed' }"
            :disabled="isHtmlFieldLocked('mode')"
            @click="setHtmlMode('embed')"
          >
            Embed
          </button>
          <button
            type="button"
            class="mode-btn"
            :class="{ active: mode === 'raw' }"
            :disabled="isHtmlFieldLocked('mode')"
            @click="setHtmlMode('raw')"
          >
            Raw
          </button>
        </div>

        <div v-if="mode === 'fetch'" class="mode-panel">
          <div class="input-row">
            <input
              type="url"
              v-model="fetchUrl"
              placeholder="https://example.com/page"
              class="url-input"
              :disabled="isHtmlFieldLocked('fetchUrl') || isHtmlFieldLocked('fetch_url')"
              :title="(isHtmlFieldLocked('fetchUrl') || isHtmlFieldLocked('fetch_url')) ? integrationLockedHint : undefined"
            />
          </div>
          <label class="selector-label">
            <span class="label-text">Content Selector</span>
            <span class="label-hint">Extract only content from a specific element</span>
          </label>
          <div class="selector-input-row">
            <input
              type="text"
              v-model="fetchSelector"
              placeholder="e.g., main, #content, .article-body"
              class="selector-input"
              :disabled="isHtmlFieldLocked('fetchSelector') || isHtmlFieldLocked('fetch_selector')"
              :title="(isHtmlFieldLocked('fetchSelector') || isHtmlFieldLocked('fetch_selector')) ? integrationLockedHint : undefined"
            />
            <div class="selector-presets">
              <button type="button" class="preset-btn" :disabled="isHtmlFieldLocked('fetchSelector') || isHtmlFieldLocked('fetch_selector')" @click="fetchSelector = 'main'" title="<main>">main</button>
              <button type="button" class="preset-btn" :disabled="isHtmlFieldLocked('fetchSelector') || isHtmlFieldLocked('fetch_selector')" @click="fetchSelector = 'article'" title="<article>">article</button>
              <button type="button" class="preset-btn" :disabled="isHtmlFieldLocked('fetchSelector') || isHtmlFieldLocked('fetch_selector')" @click="fetchSelector = '#content'" title="#content">#content</button>
              <button type="button" class="preset-btn" :disabled="isHtmlFieldLocked('fetchSelector') || isHtmlFieldLocked('fetch_selector')" @click="fetchSelector = '.content'" title=".content">.content</button>
            </div>
          </div>
          <p v-if="selectorWarning" class="selector-warning">{{ selectorWarning }}</p>
          <button
            type="button"
            class="action-btn"
            :disabled="!fetchUrl || isLoading || isHtmlFieldLocked('mode') || isHtmlFieldLocked('fetchUrl') || isHtmlFieldLocked('fetch_url')"
            @click="fetchAndSave"
          >
            {{ isLoading ? "Fetching..." : "Fetch & Save" }}
          </button>
        </div>

        <div v-if="mode === 'embed'" class="mode-panel">
          <p class="embed-hint">
            Paste full embed code from YouTube or Instagram only.
          </p>
          <textarea
            v-model="embedCode"
            class="raw-textarea"
            rows="8"
            placeholder='<iframe src="https://www.youtube.com/embed/..."></iframe>'
            :disabled="isHtmlFieldLocked('embedCode') || isHtmlFieldLocked('embed_code')"
            :title="(isHtmlFieldLocked('embedCode') || isHtmlFieldLocked('embed_code')) ? integrationLockedHint : undefined"
          ></textarea>
          <button
            type="button"
            class="action-btn"
            :disabled="isLoading"
            @click="applyEmbedAndSave"
          >
            {{ isLoading ? "Saving..." : "Apply Embed" }}
          </button>
        </div>

        <div v-if="mode === 'raw'" class="mode-panel">
          <label class="field-label">HTML</label>
          <textarea
            v-model="rawHtml"
            class="raw-textarea"
            rows="8"
            placeholder="<section><h2>Hello</h2><p>Write raw HTML content here.</p></section>"
            :disabled="isHtmlFieldLocked('rawHtml') || isHtmlFieldLocked('raw_html')"
            :title="(isHtmlFieldLocked('rawHtml') || isHtmlFieldLocked('raw_html')) ? integrationLockedHint : undefined"
          ></textarea>
          <label class="field-label">CSS</label>
          <textarea
            v-model="rawCss"
            class="raw-textarea"
            rows="5"
            placeholder="section { padding: 24px; }"
            :disabled="isHtmlFieldLocked('rawCss') || isHtmlFieldLocked('raw_css')"
            :title="(isHtmlFieldLocked('rawCss') || isHtmlFieldLocked('raw_css')) ? integrationLockedHint : undefined"
          ></textarea>
          <label class="field-label">JS</label>
          <textarea
            v-model="rawJs"
            class="raw-textarea"
            rows="5"
            placeholder="console.log('Hello from sandbox');"
            :disabled="isHtmlFieldLocked('rawJs') || isHtmlFieldLocked('raw_js')"
            :title="(isHtmlFieldLocked('rawJs') || isHtmlFieldLocked('raw_js')) ? integrationLockedHint : undefined"
          ></textarea>
          <button
            type="button"
            class="action-btn"
            :disabled="isLoading"
            @click="applyRawAndSave"
          >
            {{ isLoading ? "Saving..." : "Apply Raw Content" }}
          </button>
        </div>

        <div v-if="error" class="error-message">{{ error }}</div>
      </div>
    </template>
  </SectionBase>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { faCode } from "@fortawesome/free-solid-svg-icons";
import { useStore } from "../../store/store.js";
import * as api from "../../services/api.js";
import { isSectionIntegrationFieldLocked } from "../../utils/sectionIntegrationFieldState.js";

import SectionBase from "./_BaseSection.vue";

const props = defineProps({
  sectionKey: { type: String, default: "html" },
  sectionData: { type: Object, default: null },
});

const { state } = useStore();

const mode = ref("fetch");
const fetchUrl = ref("");
const fetchSelector = ref("");
const fetchedHtml = ref("");
const rawHtml = ref("");
const rawCss = ref("");
const rawJs = ref("");
const embedCode = ref("");
const embedProvider = ref("");
const selectorWarning = ref("");
const error = ref("");
const isLoading = ref(false);
const integrationLockedHint = "Managed by integration import.";
const previewIframe = ref(null);
const previewFrameHeight = ref(1);
const previewFrameId = `html-preview-${Math.random().toString(36).slice(2, 10)}`;

const iframeSandbox = "allow-scripts";
const PREVIEW_RESIZE_MESSAGE = "html-section-preview-resize";
const PREVIEW_MEASURE_MESSAGE = "html-section-preview-measure";

const YOUTUBE_HOSTS = [
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "youtu.be",
  "www.youtu.be",
  "youtube-nocookie.com",
  "www.youtube-nocookie.com",
];
const INSTAGRAM_HOSTS = [
  "instagram.com",
  "www.instagram.com",
  "instagr.am",
  "www.instagr.am",
  "platform.instagram.com",
];

const effectiveKey = computed(() => props.sectionKey);
const section = computed(() => {
  if (props.sectionData) return props.sectionData;
  return state.sectionsData?.[props.sectionKey] || null;
});
const isTemplateBuilderPage = computed(() =>
  String(state.pageSlug || "").startsWith("__template_")
);

function isHtmlFieldLocked(path, options = {}) {
  const normalizedPath = String(path || "").trim();
  if (!normalizedPath) return false;
  return state.isAdmin && [
    normalizedPath,
    `type_data.${normalizedPath}`,
  ].some((candidate) => isSectionIntegrationFieldLocked(section.value, candidate, options));
}

function setHtmlMode(nextMode) {
  if (isHtmlFieldLocked("mode")) return;
  mode.value = normalizeMode(nextMode);
}

const previewAvailable = computed(() => {
  if (mode.value === "fetch") return Boolean(fetchedHtml.value.trim());
  if (mode.value === "embed") return Boolean(embedCode.value.trim());
  return Boolean(rawHtml.value.trim() || rawCss.value.trim() || rawJs.value.trim());
});

const previewFrameStyle = computed(() => ({
  height: `${previewFrameHeight.value}px`,
}));

const nativeEmbedFrame = computed(() => {
  if (mode.value !== "embed") return null;
  const detectedProvider = embedProvider.value || detectEmbedProvider(embedCode.value).provider;
  if (!detectedProvider) return null;
  return buildNativeEmbedFrame(detectedProvider, embedCode.value);
});

const instagramShellClass = computed(() => {
  if (!nativeEmbedFrame.value || nativeEmbedFrame.value.provider !== "instagram") {
    return "instagram-embed-shell--post";
  }
  const kind = String(nativeEmbedFrame.value.kind || "").toLowerCase();
  if (kind === "reel" || kind === "tv") return "instagram-embed-shell--portrait";
  return "instagram-embed-shell--post";
});

const previewSrcDoc = computed(() => {
  if (!previewAvailable.value) return "";

  let bodyHtml = "";
  let css = "";
  let js = "";
  if (mode.value === "fetch") {
    bodyHtml = fetchedHtml.value;
  } else {
    bodyHtml = rawHtml.value;
    css = rawCss.value;
    js = rawJs.value;
  }

  const escapedScript = String(js || "").replace(/<\/script/gi, "<\\/script");
  const baseCssBlock = [
    "<style>",
    "html, body { margin: 0; padding: 0; }",
    "body { overflow-wrap: anywhere; }",
    "</style>",
  ].join("\n");
  const cssBlock = css ? `<style>\n${css}\n</style>` : "";
  const scriptCloseTag = "</" + "script>";
  const jsBlock = escapedScript
    ? `<script>\ntry {\n${escapedScript}\n} catch (err) { console.error(err); }\n${scriptCloseTag}`
    : "";
  const resizeScriptBlock = [
    "<script>",
    "(() => {",
    `  const frameId = ${JSON.stringify(previewFrameId)};`,
    `  const resizeType = ${JSON.stringify(PREVIEW_RESIZE_MESSAGE)};`,
    `  const measureType = ${JSON.stringify(PREVIEW_MEASURE_MESSAGE)};`,
    "  let resizeRaf = 0;",
    "  function measureHeight() {",
    "    const body = document.body;",
    "    const doc = document.documentElement;",
    "    const childBottom = body ? Array.from(body.children).reduce((max, child) => {",
    "      const rect = child.getBoundingClientRect();",
    "      return Math.max(max, rect.bottom);",
    "    }, 0) : 0;",
    "    return Math.max(",
    "      1,",
    "      body ? body.scrollHeight : 0,",
    "      body ? body.offsetHeight : 0,",
    "      doc ? doc.scrollHeight : 0,",
    "      doc ? doc.offsetHeight : 0,",
    "      childBottom",
    "    );",
    "  }",
    "  function postHeight() {",
    "    resizeRaf = 0;",
    "    window.parent.postMessage({ type: resizeType, id: frameId, height: Math.ceil(measureHeight()) }, '*');",
    "  }",
    "  function schedulePostHeight() {",
    "    if (resizeRaf) return;",
    "    resizeRaf = window.requestAnimationFrame(postHeight);",
    "  }",
    "  window.addEventListener('load', schedulePostHeight);",
    "  window.addEventListener('resize', schedulePostHeight);",
    "  window.addEventListener('message', (event) => {",
    "    if (event.data && event.data.type === measureType && event.data.id === frameId) schedulePostHeight();",
    "  });",
    "  if ('ResizeObserver' in window) {",
    "    const observer = new ResizeObserver(schedulePostHeight);",
    "    if (document.documentElement) observer.observe(document.documentElement);",
    "    if (document.body) observer.observe(document.body);",
    "  }",
    "  if ('MutationObserver' in window && document.documentElement) {",
    "    const observer = new MutationObserver(schedulePostHeight);",
    "    observer.observe(document.documentElement, { attributes: true, characterData: true, childList: true, subtree: true });",
    "  }",
    "  if (document.fonts && document.fonts.ready) {",
    "    document.fonts.ready.then(schedulePostHeight).catch(() => {});",
    "  }",
    "  schedulePostHeight();",
    "  window.setTimeout(schedulePostHeight, 100);",
    "  window.setTimeout(schedulePostHeight, 500);",
    "})();",
    scriptCloseTag,
  ].join("\n");

  return [
    "<!doctype html>",
    "<html>",
    "<head>",
    '<meta charset="utf-8" />',
    '<meta name="viewport" content="width=device-width, initial-scale=1" />',
    "<base target=\"_self\" />",
    baseCssBlock,
    cssBlock,
    "</head>",
    "<body>",
    bodyHtml,
    jsBlock,
    resizeScriptBlock,
    "</body>",
    "</html>",
  ].join("\n");
});

function requestPreviewFrameResize() {
  const frameWindow = previewIframe.value?.contentWindow;
  if (!frameWindow) return;
  frameWindow.postMessage({ type: PREVIEW_MEASURE_MESSAGE, id: previewFrameId }, "*");
}

function handlePreviewFrameMessage(event) {
  const data = event?.data;
  if (!data || data.type !== PREVIEW_RESIZE_MESSAGE || data.id !== previewFrameId) return;
  const frameWindow = previewIframe.value?.contentWindow;
  if (frameWindow && event.source && event.source !== frameWindow) return;

  const nextHeight = Math.ceil(Number(data.height));
  if (!Number.isFinite(nextHeight) || nextHeight < 1) return;
  previewFrameHeight.value = nextHeight;
}

function normalizeMode(value) {
  const text = String(value || "").trim().toLowerCase();
  if (text === "fetch" || text === "embed" || text === "raw") return text;
  return "fetch";
}

function isAllowedHost(hostname, allowedHosts) {
  const host = String(hostname || "").trim().toLowerCase();
  if (!host) return false;
  return allowedHosts.some((allowed) => host === allowed || host.endsWith(`.${allowed}`));
}

const EMBED_ATTR_URL_RE = /\b(?:src|href|data-instgrm-permalink)\s*=\s*["']((?:https?:)?\/\/[^"'<>]+)["']/gi;
const EMBED_PLAIN_URL_RE = /(?:https?:)?\/\/[^\s"'<>]+/gi;

function extractUrls(input) {
  const text = String(input || "");
  const urls = [];
  EMBED_ATTR_URL_RE.lastIndex = 0;
  let match = null;
  while ((match = EMBED_ATTR_URL_RE.exec(text)) !== null) {
    const url = String(match[1] || "").trim();
    if (!url) continue;
    urls.push(url);
  }
  if (!urls.length) {
    const plainMatches = text.match(EMBED_PLAIN_URL_RE);
    if (Array.isArray(plainMatches)) {
      for (const match of plainMatches) {
        const url = String(match || "").trim();
        if (!url) continue;
        urls.push(url);
      }
    }
  }
  return Array.from(new Set(urls));
}

function normalizeEmbedUrl(rawUrl) {
  const urlText = String(rawUrl || "").trim();
  if (!urlText) return null;
  const normalizedUrl = urlText.startsWith("//") ? `https:${urlText}` : urlText;
  try {
    return new URL(normalizedUrl);
  } catch {
    return null;
  }
}

function extractInstagramPermalink(url) {
  const match = String(url?.pathname || "").match(/^\/(reel|p|tv)\/([A-Za-z0-9_-]+)(?:\/|$)/);
  if (!match) return null;
  return {
    kind: match[1],
    id: match[2],
  };
}

function extractYoutubeVideoId(url) {
  const host = String(url?.hostname || "").toLowerCase();
  const path = String(url?.pathname || "");
  const YT_ID_RE = /^[A-Za-z0-9_-]{11}$/;

  if (host === "youtu.be" || host.endsWith(".youtu.be")) {
    const id = path.split("/").filter(Boolean)[0] || "";
    return YT_ID_RE.test(id) ? id : "";
  }

  if (host.includes("youtube.com") || host.includes("youtube-nocookie.com")) {
    if (path === "/watch") {
      const id = String(url.searchParams.get("v") || "").trim();
      return YT_ID_RE.test(id) ? id : "";
    }
    const segments = path.split("/").filter(Boolean);
    if (segments[0] === "embed" || segments[0] === "shorts" || segments[0] === "live") {
      const id = String(segments[1] || "").trim();
      return YT_ID_RE.test(id) ? id : "";
    }
  }

  return "";
}

function buildNativeEmbedFrame(provider, code) {
  const urls = extractUrls(code);
  if (!urls.length) return null;

  if (provider === "instagram") {
    for (const rawUrl of urls) {
      const url = normalizeEmbedUrl(rawUrl);
      if (!url) continue;
      if (!isAllowedHost(url.hostname, INSTAGRAM_HOSTS)) continue;
      const permalink = extractInstagramPermalink(url);
      if (!permalink) continue;
      const src = `https://www.instagram.com/${permalink.kind}/${permalink.id}/embed/`;
      return { provider: "instagram", src, kind: permalink.kind };
    }
    return null;
  }

  if (provider === "youtube") {
    for (const rawUrl of urls) {
      const url = normalizeEmbedUrl(rawUrl);
      if (!url) continue;
      if (!isAllowedHost(url.hostname, YOUTUBE_HOSTS)) continue;
      const videoId = extractYoutubeVideoId(url);
      if (!videoId) continue;
      const src = `https://www.youtube-nocookie.com/embed/${videoId}?rel=0&modestbranding=1&playsinline=1`;
      return { provider: "youtube", src };
    }
    return null;
  }

  return null;
}

function detectEmbedProvider(code) {
  const urls = extractUrls(code);
  const providers = new Set();

  for (const rawUrl of urls) {
    let host = "";
    try {
      const normalizedUrl = rawUrl.startsWith("//") ? `https:${rawUrl}` : rawUrl;
      host = new URL(normalizedUrl).hostname || "";
    } catch {
      continue;
    }
    if (isAllowedHost(host, YOUTUBE_HOSTS)) {
      providers.add("youtube");
    } else if (isAllowedHost(host, INSTAGRAM_HOSTS)) {
      providers.add("instagram");
    } else {
      return { provider: "", invalidHost: host };
    }
  }

  if (providers.size !== 1) {
    return { provider: "", invalidHost: providers.size === 0 ? "none" : "multiple" };
  }

  return { provider: Array.from(providers)[0], invalidHost: "" };
}

function initFromSectionData() {
  const typeData = section.value?.type_data || {};
  fetchUrl.value = String(typeData.fetch_url || typeData.source_url || "");
  fetchSelector.value = String(typeData.fetch_selector || typeData.html_selector || "");
  fetchedHtml.value = String(typeData.fetched_html || typeData.rendered_html || "");
  rawHtml.value = String(typeData.raw_html || "");
  rawCss.value = String(typeData.raw_css || "");
  rawJs.value = String(typeData.raw_js || "");
  embedCode.value = String(typeData.embed_code || "");
  embedProvider.value = String(typeData.embed_provider || "");

  if (!rawHtml.value) {
    const sourceType = String(typeData.source_type || "").toLowerCase();
    if (sourceType === "html" && !fetchUrl.value) {
      rawHtml.value = String(typeData.raw_content || typeData.rendered_html || "");
    }
  }

  if (!embedProvider.value && embedCode.value) {
    const detected = detectEmbedProvider(embedCode.value);
    embedProvider.value = detected.provider || "";
  }

  const explicitMode = normalizeMode(typeData.mode);
  if (typeData.mode) {
    mode.value = explicitMode;
  } else if (embedCode.value.trim()) {
    mode.value = "embed";
  } else if (fetchUrl.value.trim()) {
    mode.value = "fetch";
  } else {
    mode.value = "raw";
  }
}

watch(
  () => JSON.stringify(section.value?.type_data || {}),
  () => {
    initFromSectionData();
  },
  { immediate: true }
);

watch(
  previewSrcDoc,
  () => {
    previewFrameHeight.value = 1;
    nextTick(() => requestPreviewFrameResize());
  }
);

onMounted(() => {
  window.addEventListener("message", handlePreviewFrameMessage);
  initFromSectionData();
  nextTick(() => requestPreviewFrameResize());
});

onBeforeUnmount(() => {
  window.removeEventListener("message", handlePreviewFrameMessage);
});

async function fetchAndSave() {
  if (!fetchUrl.value) return;

  isLoading.value = true;
  error.value = "";
  selectorWarning.value = "";
  try {
    const result = await api.parseMarkdown({
      source_url: fetchUrl.value,
      source_type: "html",
      html_selector: fetchSelector.value,
    });
    fetchedHtml.value = String(result.rendered_html || "");
    if (!isHtmlFieldLocked("mode")) mode.value = "fetch";
    if (fetchSelector.value && result.selector_found === false) {
      selectorWarning.value = `Selector "${fetchSelector.value}" not found. Showing full content.`;
    }
    await saveTypeData({
      mode: "fetch",
      fetch_url: fetchUrl.value,
      fetch_selector: fetchSelector.value,
      fetched_html: fetchedHtml.value,
    });
  } catch (err) {
    error.value = err.message || "Failed to fetch HTML";
    console.error("Failed to fetch HTML:", err);
  } finally {
    isLoading.value = false;
  }
}

async function applyRawAndSave() {
  isLoading.value = true;
  error.value = "";
  selectorWarning.value = "";
  try {
    if (!isHtmlFieldLocked("mode")) mode.value = "raw";
    await saveTypeData({
      mode: "raw",
      raw_html: rawHtml.value,
      raw_css: rawCss.value,
      raw_js: rawJs.value,
    });
  } catch (err) {
    error.value = err.message || "Failed to save raw content";
    console.error("Failed to save raw content:", err);
  } finally {
    isLoading.value = false;
  }
}

async function applyEmbedAndSave() {
  isLoading.value = true;
  error.value = "";
  selectorWarning.value = "";
  try {
    if (!embedCode.value.trim()) {
      throw new Error("Paste embed code first.");
    }
    const detected = detectEmbedProvider(embedCode.value);
    if (!detected.provider) {
      if (detected.invalidHost === "none") {
        throw new Error("Embed code must include a valid YouTube or Instagram URL.");
      }
      if (detected.invalidHost === "multiple") {
        throw new Error("Embed code can only contain one provider at a time.");
      }
      throw new Error(`Unsupported embed host "${detected.invalidHost}". Only YouTube and Instagram are allowed.`);
    }
    if (!isHtmlFieldLocked("embedProvider") && !isHtmlFieldLocked("embed_provider")) {
      embedProvider.value = detected.provider;
    }
    if (!isHtmlFieldLocked("mode")) mode.value = "embed";
    await saveTypeData({
      mode: "embed",
      embed_code: embedCode.value,
      embed_provider: embedProvider.value,
    });
  } catch (err) {
    error.value = err.message || "Failed to save embed code";
    console.error("Failed to save embed code:", err);
  } finally {
    isLoading.value = false;
  }
}

async function saveTypeData(overrides = {}) {
  const sectionId = state.sectionIds?.[effectiveKey.value];
  if (!sectionId) {
    console.warn("No section ID found for key:", effectiveKey.value);
    return;
  }

  const existingTypeData = section.value?.type_data || {};
  const canonicalTypeData = {
    mode: mode.value,
    fetch_url: fetchUrl.value,
    fetch_selector: fetchSelector.value,
    fetched_html: fetchedHtml.value,
    raw_html: rawHtml.value,
    raw_css: rawCss.value,
    raw_js: rawJs.value,
    embed_code: embedCode.value,
    embed_provider: embedProvider.value,
    ...overrides,
  };
  const filteredTypeData = filterLockedHtmlTypeData(canonicalTypeData);
  const nextTypeData = {
    ...existingTypeData,
    ...filteredTypeData,
  };

  delete nextTypeData.body;
  delete nextTypeData.description;
  delete nextTypeData.source_url;
  delete nextTypeData.source_type;
  delete nextTypeData.raw_content;
  delete nextTypeData.raw_markdown;
  delete nextTypeData.rendered_html;
  delete nextTypeData.html_selector;

  await api.updateSection(sectionId, {
    type_data: nextTypeData,
    revision_change_kind: "content",
  });
}

function filterLockedHtmlTypeData(typeData) {
  const next = { ...(typeData || {}) };
  const lockAliases = {
    mode: ["mode"],
    fetch_url: ["fetchUrl", "fetch_url"],
    fetch_selector: ["fetchSelector", "fetch_selector"],
    fetched_html: ["fetchedHtml", "fetched_html"],
    raw_html: ["rawHtml", "raw_html"],
    raw_css: ["rawCss", "raw_css"],
    raw_js: ["rawJs", "raw_js"],
    embed_code: ["embedCode", "embed_code"],
    embed_provider: ["embedProvider", "embed_provider"],
  };
  Object.entries(lockAliases).forEach(([key, aliases]) => {
    if (aliases.some((alias) => isHtmlFieldLocked(alias))) {
      delete next[key];
    }
  });
  return next;
}
</script>

<style scoped>
.html-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.html-preview-wrap {
  overflow: hidden;
}

.html-preview-wrap--embed {
  padding: 10px;
}

.html-preview-wrap--instagram {
  display: flex;
  justify-content: center;
}

.html-preview-frame {
  width: 100%;
  min-height: 0;
  border: 0;
  background: #fff;
  display: block;
}

.instagram-embed-shell {
  width: min(100%, 540px);
  margin: 0 auto;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}

.instagram-embed-shell--portrait {
  aspect-ratio: 9 / 16;
}

.instagram-embed-shell--post {
  aspect-ratio: 4 / 5;
}

.html-preview-frame--instagram {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: block;
}

.youtube-wrap {
  position: relative;
  width: min(100%, 960px);
  margin: 0 auto;
  aspect-ratio: 16 / 9;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
}

.html-preview-frame--youtube {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  min-height: 0;
  border: 0;
  display: block;
}

@media (max-width: 680px) {
  .html-preview-wrap--embed {
    padding: 6px;
  }
}

.html-controls {
  background: var(--surface-2);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mode-switch {
  display: flex;
  gap: 8px;
}

.mode-btn {
  flex: 1;
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: #fff;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.mode-btn:hover {
  background: var(--surface, #e5e7eb);
}

.mode-btn.active {
  background: var(--accent, #5b2fe3);
  color: #fff;
  border-color: var(--accent, #5b2fe3);
}

.mode-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-row {
  display: flex;
  gap: 8px;
}

.url-input {
  width: 100%;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid var(--border);
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s ease;
}

.url-input:focus {
  border-color: var(--accent, #5b2fe3);
}

.selector-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.label-text {
  font-weight: 600;
  font-size: 13px;
  color: var(--text);
}

.label-hint {
  font-size: 12px;
  color: var(--muted);
}

.selector-input-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.selector-input {
  flex: 1;
  min-width: 200px;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  outline: none;
  transition: border-color 0.15s ease;
}

.selector-input:focus {
  border-color: var(--accent, #5b2fe3);
}

.selector-presets {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.preset-btn {
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s ease;
}

.preset-btn:hover {
  background: var(--accent, #5b2fe3);
  color: #fff;
  border-color: var(--accent, #5b2fe3);
}

.selector-warning {
  margin: 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fef3c7;
  color: #92400e;
  font-size: 12px;
}

.embed-hint {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}

.field-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
  color: var(--muted);
}

.raw-textarea {
  width: 100%;
  padding: 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s ease;
}

.raw-textarea:focus {
  border-color: var(--accent, #5b2fe3);
}

.action-btn {
  padding: 12px 20px;
  border-radius: 10px;
  background: var(--accent, #5b2fe3);
  color: #fff;
  border: none;
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.action-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent, #5b2fe3) 85%, black);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-message {
  padding: 10px 14px;
  border-radius: 8px;
  background: #fee2e2;
  color: #dc2626;
  font-size: 13px;
  font-weight: 500;
}

.empty-content {
  padding: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: var(--muted);
  font-size: 14px;
  background: var(--surface-2);
  border-radius: 12px;
}

.empty-icon {
  font-size: 32px;
  opacity: 0.5;
}
</style>
