export function clamp(value, min, max, fallback = min) {
  const num = Number(value);
  if (!Number.isFinite(num)) return fallback;
  return Math.max(min, Math.min(max, num));
}

export function normalizeTransform(transform = {}) {
  return {
    zoom: clamp(transform.zoom, 1, 4, 1),
    focalX: clamp(transform.focalX, 0, 100, 50),
    focalY: clamp(transform.focalY, 0, 100, 50),
    rotation: clamp(transform.rotation, -180, 180, 0),
  };
}

export function normalizeRatio(value, fallback = "16:9") {
  const ratio = String(value || "").trim();
  if (["1:1", "3:2", "4:3", "16:9", "2:3", "3:4", "4:5"].includes(ratio)) return ratio;
  return fallback;
}

export function ratioToCss(ratio, direction = "landscape") {
  const safeRatio = normalizeRatio(ratio);
  const map = {
    "1:1": [1, 1],
    "3:2": [3, 2],
    "4:3": [4, 3],
    "16:9": [16, 9],
    "2:3": [2, 3],
    "3:4": [3, 4],
    "4:5": [4, 5],
  };
  const [w, h] = map[safeRatio] || [16, 9];
  const portrait = String(direction || "").toLowerCase() === "portrait";
  return portrait ? `${h} / ${w}` : `${w} / ${h}`;
}

export function parseAspectRatio(value, fallback = 16 / 9) {
  const raw = String(value || "").trim();
  if (!raw.includes("/")) return fallback;
  const [leftRaw, rightRaw] = raw.split("/").map((part) => Number(part.trim()));
  if (!Number.isFinite(leftRaw) || !Number.isFinite(rightRaw) || rightRaw === 0) return fallback;
  const ratio = leftRaw / rightRaw;
  if (!Number.isFinite(ratio) || ratio <= 0) return fallback;
  return ratio;
}

export function calculateRotationGuardScale(rotation = 0, aspectRatio = 16 / 9) {
  const safeAspect = clamp(aspectRatio, 0.05, 20, 16 / 9);
  const angle = Math.abs(clamp(rotation, -180, 180, 0)) * (Math.PI / 180);
  if (angle === 0) return 1;
  const cos = Math.abs(Math.cos(angle));
  const sin = Math.abs(Math.sin(angle));
  const coverX = cos + sin / safeAspect;
  const coverY = cos + sin * safeAspect;
  const guard = Math.max(coverX, coverY, 1);
  if (!Number.isFinite(guard)) return 1;
  return guard;
}

export function buildImageTransformStyle({ zoom = 1, focalX = 50, focalY = 50 } = {}) {
  const safe = normalizeTransform({ zoom, focalX, focalY, rotation: 0 });
  const transforms = [];
  if (safe.zoom !== 1) transforms.push(`scale(${safe.zoom})`);
  return {
    objectPosition: `${safe.focalX}% ${safe.focalY}%`,
    transform: transforms.length > 0 ? transforms.join(" ") : "none",
    transformOrigin: `${safe.focalX}% ${safe.focalY}%`,
  };
}
