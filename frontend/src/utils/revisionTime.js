import * as api from "../services/api.js";

const TZ_SUFFIX_PATTERN = /(Z|[+-]\d{2}:\d{2})$/i;
const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const WALL_DATETIME_PATTERN = /^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/;
export const DEFAULT_SERVER_TIMEZONE = "Europe/Berlin";
const DEFAULT_SYNC_INTERVAL_MS = 60 * 60 * 1000;

let serverTimezone = DEFAULT_SERVER_TIMEZONE;
let serverOffsetMs = 0;
let lastSyncedAtMs = null;
let syncPromise = null;
let syncInterval = null;

function applyServerTimePayload(payload) {
  if (!payload || typeof payload !== "object") return false;

  const tzCandidate = String(payload.server_timezone || "").trim();
  if (tzCandidate) {
    serverTimezone = tzCandidate;
  }

  const serverTimeRaw = payload.server_time;
  if (!serverTimeRaw) return true;

  const serverDate = new Date(serverTimeRaw);
  if (Number.isNaN(serverDate.getTime())) return true;

  serverOffsetMs = serverDate.getTime() - Date.now();
  lastSyncedAtMs = Date.now();
  return true;
}

export async function syncServerClock() {
  if (syncPromise) return syncPromise;

  syncPromise = (async () => {
    const payload = await api.getServerTime();
    applyServerTimePayload(payload);
    return getServerClockState();
  })();

  try {
    return await syncPromise;
  } finally {
    syncPromise = null;
  }
}

export function startServerClockSync({ intervalMs = DEFAULT_SYNC_INTERVAL_MS } = {}) {
  if (syncInterval) {
    clearInterval(syncInterval);
    syncInterval = null;
  }

  const firstSync = syncServerClock().catch((err) => {
    console.error("Failed to sync server clock:", err);
    return getServerClockState();
  });

  syncInterval = setInterval(() => {
    void syncServerClock().catch((err) => {
      console.error("Failed to sync server clock:", err);
    });
  }, Math.max(30_000, Number(intervalMs) || DEFAULT_SYNC_INTERVAL_MS));

  return firstSync;
}

export function stopServerClockSync() {
  if (syncInterval) {
    clearInterval(syncInterval);
    syncInterval = null;
  }
}

export function getServerTimezone() {
  return serverTimezone || DEFAULT_SERVER_TIMEZONE;
}

export function getCurrentServerDate() {
  return new Date(Date.now() + serverOffsetMs);
}

function getDateTimePartsInServerTimezone(value = getCurrentServerDate()) {
  const raw = typeof value === "string" ? value.trim() : "";
  const normalizedValue = raw && !TZ_SUFFIX_PATTERN.test(raw) ? `${raw}Z` : value;
  const source = value instanceof Date ? value : new Date(normalizedValue);
  if (Number.isNaN(source.getTime())) return null;
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: getServerTimezone(),
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    }).formatToParts(source);
    const getPart = (type) => parts.find((part) => part.type === type)?.value;
    const year = Number.parseInt(getPart("year"), 10);
    const month = Number.parseInt(getPart("month"), 10);
    const day = Number.parseInt(getPart("day"), 10);
    const hour = Number.parseInt(getPart("hour"), 10);
    const minute = Number.parseInt(getPart("minute"), 10);
    const second = Number.parseInt(getPart("second"), 10);
    if (![year, month, day, hour, minute, second].every(Number.isFinite)) return null;
    return { year, month, day, hour, minute, second };
  } catch {
    return null;
  }
}

function getTimeZoneOffsetMs(timeZone, value) {
  const source = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(source.getTime())) return 0;
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    }).formatToParts(source);
    const getPart = (type) => parts.find((part) => part.type === type)?.value;
    const year = Number.parseInt(getPart("year"), 10);
    const month = Number.parseInt(getPart("month"), 10);
    const day = Number.parseInt(getPart("day"), 10);
    const hour = Number.parseInt(getPart("hour"), 10);
    const minute = Number.parseInt(getPart("minute"), 10);
    const second = Number.parseInt(getPart("second"), 10);
    if (![year, month, day, hour, minute, second].every(Number.isFinite)) return 0;
    const wallAsUtcMs = Date.UTC(year, month - 1, day, hour, minute, second);
    return wallAsUtcMs - source.getTime();
  } catch {
    return 0;
  }
}

export function getCurrentServerWallDate(value = getCurrentServerDate()) {
  const parts = getDateTimePartsInServerTimezone(value);
  if (!parts) return getCurrentServerDate();
  return new Date(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
}

export function getCurrentServerDateISO() {
  const parts = getDateTimePartsInServerTimezone();
  if (!parts) return getCurrentServerDate().toISOString().slice(0, 10);
  return [
    String(parts.year).padStart(4, "0"),
    String(parts.month).padStart(2, "0"),
    String(parts.day).padStart(2, "0"),
  ].join("-");
}

export function formatDateTimeLocalForServerTimezone(value) {
  const parts = getDateTimePartsInServerTimezone(value);
  if (!parts) return "";
  return [
    [
      String(parts.year).padStart(4, "0"),
      String(parts.month).padStart(2, "0"),
      String(parts.day).padStart(2, "0"),
    ].join("-"),
    [
      String(parts.hour).padStart(2, "0"),
      String(parts.minute).padStart(2, "0"),
    ].join(":"),
  ].join("T");
}

export const DATE_PICKER_DATE_TIME_DISPLAY_FORMAT = "dd.MM.yy, HH:mm";
export const DATE_PICKER_DATE_TIME_DISPLAY_FORMATS = Object.freeze({
  input: DATE_PICKER_DATE_TIME_DISPLAY_FORMAT,
  preview: DATE_PICKER_DATE_TIME_DISPLAY_FORMAT,
});
export const DATE_PICKER_TEXT_INPUT_OPTIONS = Object.freeze({
  format: DATE_PICKER_DATE_TIME_DISPLAY_FORMAT,
  maskFormat: DATE_PICKER_DATE_TIME_DISPLAY_FORMAT,
});
export const DATE_PICKER_DATE_ONLY_DISPLAY_FORMAT = "dd.MM.yyyy";
export const DATE_PICKER_DATE_ONLY_DISPLAY_FORMATS = Object.freeze({
  input: DATE_PICKER_DATE_ONLY_DISPLAY_FORMAT,
  preview: DATE_PICKER_DATE_ONLY_DISPLAY_FORMAT,
});
export const DATE_PICKER_DATE_ONLY_TEXT_INPUT_OPTIONS = Object.freeze({
  format: DATE_PICKER_DATE_ONLY_DISPLAY_FORMAT,
  maskFormat: DATE_PICKER_DATE_ONLY_DISPLAY_FORMAT,
});

export function getServerClockState() {
  return {
    timezone: getServerTimezone(),
    offsetMs: serverOffsetMs,
    lastSyncedAtMs,
  };
}

export function parseRevisionTimestamp(value) {
  if (!value) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  const raw = String(value).trim();
  if (!raw) return null;
  // If timezone info is missing, treat timestamps as UTC to avoid local-time drift.
  const normalized = TZ_SUFFIX_PATTERN.test(raw) ? raw : `${raw}Z`;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function parseServerDateOnlyParts(value) {
  const match = String(value || "").trim().match(DATE_ONLY_PATTERN);
  if (!match) return null;
  const year = Number.parseInt(match[1], 10);
  const month = Number.parseInt(match[2], 10);
  const day = Number.parseInt(match[3], 10);
  if (![year, month, day].every(Number.isFinite)) return null;
  return { year, month, day };
}

function formatServerDateOnlyParts(parts) {
  if (!parts) return "";
  return [
    String(parts.year).padStart(4, "0"),
    String(parts.month).padStart(2, "0"),
    String(parts.day).padStart(2, "0"),
  ].join("-");
}

export function serverDateOnlyToLocalDate(value) {
  const parts = parseServerDateOnlyParts(value);
  if (!parts) return null;
  const parsed = new Date(parts.year, parts.month - 1, parts.day);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function localDateToServerDateOnly(value) {
  if (value == null || value === "") return "";
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return formatServerDateOnlyParts({
      year: value.getFullYear(),
      month: value.getMonth() + 1,
      day: value.getDate(),
    });
  }

  const raw = String(value || "").trim();
  if (!raw) return "";
  const dateOnlyParts = parseServerDateOnlyParts(raw.slice(0, 10));
  if (dateOnlyParts) return formatServerDateOnlyParts(dateOnlyParts);

  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return "";
  return formatServerDateOnlyParts({
    year: parsed.getFullYear(),
    month: parsed.getMonth() + 1,
    day: parsed.getDate(),
  });
}

export function localDateToServerWallDateTime(value) {
  if (value == null || value === "") return "";
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return [
      [
        String(value.getFullYear()).padStart(4, "0"),
        String(value.getMonth() + 1).padStart(2, "0"),
        String(value.getDate()).padStart(2, "0"),
      ].join("-"),
      [
        String(value.getHours()).padStart(2, "0"),
        String(value.getMinutes()).padStart(2, "0"),
      ].join(":"),
    ].join("T");
  }

  return normalizeServerWallDateTimeValue(value);
}

export function parseServerWallDateTimeParts(value) {
  const raw = String(value || "").trim();
  if (TZ_SUFFIX_PATTERN.test(raw)) return null;
  const match = raw.match(WALL_DATETIME_PATTERN);
  if (!match) return null;
  const year = Number.parseInt(match[1], 10);
  const month = Number.parseInt(match[2], 10);
  const day = Number.parseInt(match[3], 10);
  const hour = Number.parseInt(match[4], 10);
  const minute = Number.parseInt(match[5], 10);
  if (![year, month, day, hour, minute].every(Number.isFinite)) return null;
  return { year, month, day, hour, minute };
}

export function serverWallDateTimeToLocalDate(value) {
  const raw = String(value || "").trim();
  const normalizedValue = TZ_SUFFIX_PATTERN.test(raw)
    ? formatDateTimeLocalForServerTimezone(raw)
    : raw;
  const parts = parseServerWallDateTimeParts(normalizedValue);
  if (!parts) return null;
  const parsed = new Date(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function normalizeServerWallDateTimeValue(value) {
  if (value == null) return "";
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return formatDateTimeLocalForServerTimezone(value);
  }
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (TZ_SUFFIX_PATTERN.test(raw)) {
    return formatDateTimeLocalForServerTimezone(raw);
  }
  const parts = parseServerWallDateTimeParts(raw);
  if (!parts) return raw;
  return [
    [
      String(parts.year).padStart(4, "0"),
      String(parts.month).padStart(2, "0"),
      String(parts.day).padStart(2, "0"),
    ].join("-"),
    [
      String(parts.hour).padStart(2, "0"),
      String(parts.minute).padStart(2, "0"),
    ].join(":"),
  ].join("T");
}

export function serverWallDateTimeToInstantDate(value) {
  const parts = parseServerWallDateTimeParts(value);
  if (!parts) return null;
  const wallAsUtcMs = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute);
  const firstOffset = getTimeZoneOffsetMs(getServerTimezone(), new Date(wallAsUtcMs));
  let instant = new Date(wallAsUtcMs - firstOffset);
  const secondOffset = getTimeZoneOffsetMs(getServerTimezone(), instant);
  if (secondOffset !== firstOffset) {
    instant = new Date(wallAsUtcMs - secondOffset);
  }
  return Number.isNaN(instant.getTime()) ? null : instant;
}

export function formatServerDateOnly(value, options = {}, { locale = "de-DE", fallback = "" } = {}) {
  const parts = parseServerDateOnlyParts(value);
  if (!parts) return fallback;
  const parsed = new Date(Date.UTC(parts.year, parts.month - 1, parts.day, 12));
  return parsed.toLocaleDateString(locale, {
    timeZone: "UTC",
    ...options,
  });
}

export function formatServerWallTime(value, options = {}, { locale = "de-DE", fallback = "" } = {}) {
  const parts = parseServerWallDateTimeParts(value);
  if (!parts) return fallback;
  const parsed = new Date(Date.UTC(1970, 0, 1, parts.hour, parts.minute));
  const useStyleOptions = Boolean(options.dateStyle || options.timeStyle);
  return parsed.toLocaleTimeString(locale, {
    ...(useStyleOptions ? {} : {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      hourCycle: "h23",
    }),
    timeZone: "UTC",
    ...options,
  });
}

export function formatInstantInServerTimezone(value, options = {}, { locale = "de-DE", fallback = "" } = {}) {
  const parsed = parseRevisionTimestamp(value);
  if (!parsed) return fallback;
  const useStyleOptions = Boolean(options.dateStyle || options.timeStyle);
  return parsed.toLocaleString(locale, {
    ...(useStyleOptions ? {} : {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }),
    timeZone: getServerTimezone(),
    ...options,
  });
}

export function getRevisionTimestampMs(value) {
  const parsed = parseRevisionTimestamp(value);
  return parsed ? parsed.getTime() : 0;
}

export function formatRevisionTimestampBerlin(value, options = {}) {
  return formatInstantInServerTimezone(value, options, { fallback: null });
}
