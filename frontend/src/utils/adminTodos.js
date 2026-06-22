export const TODO_PRIORITY_VALUES = ["urgent", "needed", "optional"];
export const DEFAULT_TODO_PRIORITY = "needed";
export const DEFAULT_TODO_TAG_ID = "text";

export const TODO_PRIORITY_META = Object.freeze({
  urgent: { label: "Urgent", icon: ["fas", "angles-up"] },
  needed: { label: "Needed", icon: ["fas", "angle-up"] },
  optional: { label: "Optional", icon: ["fas", "genderless"] },
});

export const DEVOPS_DEFAULT_TODO_TAGS = [
  { id: "bug", area: "it" },
  { id: "feature", area: "it" },
  { id: "improve", area: "it" },
  { id: "media", area: "content" },
  { id: "text", area: "content" },
];

export const DEFAULT_TODO_TAG_META = Object.freeze({
  bug: { label: "Bug", icon: ["fas", "bug"] },
  feature: { label: "Feature", icon: ["fas", "star"] },
  improve: { label: "Improve", icon: ["fas", "arrow-trend-up"] },
  media: { label: "Media", icon: ["fas", "image"] },
  text: { label: "Text", icon: ["fas", "font"] },
});

export function todoPriorityLabel(priority) {
  return TODO_PRIORITY_META[priority]?.label || TODO_PRIORITY_META[DEFAULT_TODO_PRIORITY].label;
}

export function todoPriorityIcon(priority) {
  return TODO_PRIORITY_META[priority]?.icon || TODO_PRIORITY_META[DEFAULT_TODO_PRIORITY].icon;
}

export function todoPriorityIconLabel(priority) {
  return `Urgency: ${todoPriorityLabel(priority)}`;
}

export function todoPriorityOptionLabel(priority) {
  return todoPriorityLabel(priority);
}

export function todoPrioritySelectOption(priority) {
  return {
    value: priority,
    label: todoPriorityOptionLabel(priority),
    icon: todoPriorityIcon(priority),
    iconLabel: todoPriorityIconLabel(priority),
  };
}

export function todoTagMeta(tagId) {
  return DEFAULT_TODO_TAG_META[String(tagId || "").trim()] || null;
}

export function todoTagIcon(tagId) {
  return todoTagMeta(tagId)?.icon || null;
}

export function todoTagText(tagId) {
  const normalized = String(tagId || "").trim();
  return todoTagMeta(normalized)?.label || normalized || DEFAULT_TODO_TAG_ID;
}

export function todoTagIconLabel(tagId) {
  return `Todo type: ${todoTagText(tagId)}`;
}

export function todoTagOptionLabel(tagId) {
  return todoTagText(tagId);
}

export function todoTagSelectOption(tagId) {
  const value = String(tagId || "").trim() || DEFAULT_TODO_TAG_ID;
  return {
    value,
    label: todoTagOptionLabel(value),
    icon: todoTagIcon(value),
    iconLabel: todoTagIconLabel(value),
  };
}

function asTrimmedString(value) {
  return String(value ?? "").trim();
}

function toCamelCase(value) {
  return String(value || "").replace(/_([a-z0-9])/g, (_, letter) => letter.toUpperCase());
}

function convertKeysToCamel(value) {
  if (Array.isArray(value)) return value.map((item) => convertKeysToCamel(item));
  if (value && typeof value === "object") {
    const next = {};
    Object.entries(value).forEach(([key, nestedValue]) => {
      next[toCamelCase(key)] = convertKeysToCamel(nestedValue);
    });
    return next;
  }
  return value;
}

function parsePriority(value) {
  const priority = asTrimmedString(value);
  return TODO_PRIORITY_VALUES.includes(priority) ? priority : DEFAULT_TODO_PRIORITY;
}

function parsePriorityRank(value) {
  if (value == null || value === "") return null;
  const rank = Number(value);
  if (!Number.isFinite(rank) || rank < 0) return null;
  return Math.floor(rank);
}

function normalizeTodoComments(rawComments) {
  if (!Array.isArray(rawComments)) return [];
  return rawComments
    .map((rawComment, index) => {
      const source = rawComment && typeof rawComment === "object"
        ? convertKeysToCamel(rawComment)
        : {};
      const text = asTrimmedString(source?.text);
      if (!text) return null;
      return {
        id: asTrimmedString(source?.id) || `comment-${Date.now()}-${index}`,
        text,
        createdBy: asTrimmedString(source?.createdBy ?? "unknown") || "unknown",
        createdAt: asTrimmedString(source?.createdAt) || null,
      };
    })
    .filter(Boolean);
}

function fillMissingPriorityRanks(items) {
  const counters = {
    urgent: 0,
    needed: 0,
    optional: 0,
  };
  return items.map((item) => {
    const priority = parsePriority(item.priority);
    const next = { ...item, priority };
    if (next.priorityRank == null) {
      next.priorityRank = counters[priority];
    }
    counters[priority] += 1;
    return next;
  });
}

export function normalizeTodoTags(rawTags) {
  const normalized = [];
  const seen = new Set();
  const defaultAreaById = Object.fromEntries(
    DEVOPS_DEFAULT_TODO_TAGS.map((tag) => [tag.id, tag.area])
  );

  for (const defaultTag of DEVOPS_DEFAULT_TODO_TAGS) {
    normalized.push({ ...defaultTag });
    seen.add(defaultTag.id);
  }

  if (!Array.isArray(rawTags)) return normalized;
  for (const raw of rawTags) {
    if (!raw || typeof raw !== "object") continue;
    const id = asTrimmedString(raw.id);
    if (!id || seen.has(id)) continue;
    const area = asTrimmedString(raw.area).toLowerCase();
    if (area !== "it" && area !== "content") continue;
    normalized.push({ id, area });
    seen.add(id);
  }

  for (let i = 0; i < normalized.length; i += 1) {
    const tag = normalized[i];
    if (defaultAreaById[tag.id]) {
      normalized[i] = { id: tag.id, area: defaultAreaById[tag.id] };
    }
  }

  return normalized;
}

export function getTodoTagAreaMap(tags) {
  const map = {};
  for (const tag of normalizeTodoTags(tags)) {
    map[tag.id] = tag.area;
  }
  return map;
}

export function isDefaultTodoTag(tagId) {
  return DEVOPS_DEFAULT_TODO_TAGS.some((tag) => tag.id === tagId);
}

export function normalizeTodoItem(todo, index = 0, { defaultTagId = DEFAULT_TODO_TAG_ID } = {}) {
  const source = todo && typeof todo === "object" ? convertKeysToCamel(todo) : {};
  const text = asTrimmedString(source?.text);
  const createdBy = asTrimmedString(source?.createdBy ?? "unknown") || "unknown";
  const createdAt = asTrimmedString(source?.createdAt) || null;
  const resolvedBy = asTrimmedString(source?.resolvedBy) || null;
  const resolvedAt = asTrimmedString(source?.resolvedAt) || null;
  const tag = asTrimmedString(source?.tag) || defaultTagId;
  return {
    id: asTrimmedString(source?.id) || `${Date.now()}-${index}`,
    text,
    done: Boolean(source?.done ?? false),
    createdBy,
    createdAt,
    resolvedBy,
    resolvedAt,
    tag,
    priority: parsePriority(source?.priority),
    priorityRank: parsePriorityRank(source?.priorityRank),
    comments: normalizeTodoComments(source?.comments),
  };
}

export function normalizeTodoList(todos, { defaultTagId = DEFAULT_TODO_TAG_ID } = {}) {
  if (!Array.isArray(todos)) return [];
  const normalized = todos
    .map((todo, index) => normalizeTodoItem(todo, index, { defaultTagId }))
    .filter((todo) => todo.text.length > 0);
  return fillMissingPriorityRanks(normalized);
}

export function serializeTodoItem(todo) {
  const normalized = normalizeTodoItem(todo, 0);
  return {
    id: normalized.id,
    text: normalized.text,
    done: normalized.done,
    created_by: normalized.createdBy,
    created_at: normalized.createdAt,
    resolved_by: normalized.resolvedBy,
    resolved_at: normalized.resolvedAt,
    tag: normalized.tag || DEFAULT_TODO_TAG_ID,
    priority: parsePriority(normalized.priority),
    priority_rank: parsePriorityRank(normalized.priorityRank) ?? 0,
    comments: normalizeTodoComments(normalized.comments).map((comment) => ({
      id: comment.id,
      text: comment.text,
      created_by: comment.createdBy,
      created_at: comment.createdAt,
    })),
  };
}

export function serializeTodoList(todos) {
  return normalizeTodoList(todos).map((todo) => serializeTodoItem(todo));
}

export function normalizeTodoTagId(rawValue) {
  return asTrimmedString(rawValue).replace(/\s+/g, "");
}
