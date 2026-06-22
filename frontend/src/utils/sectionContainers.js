export const SECTION_CONTAINER_TARGET_PREFIX = "__container__:";

function normalizeText(value) {
  const text = String(value || "").trim();
  return text || null;
}

function uniqueOrdered(values = []) {
  const result = [];
  const seen = new Set();
  for (const raw of values) {
    const value = normalizeText(raw);
    if (!value || seen.has(value)) continue;
    seen.add(value);
    result.push(value);
  }
  return result;
}

function keyBySectionId(sectionIds = {}) {
  const map = {};
  for (const [key, rawSectionId] of Object.entries(sectionIds || {})) {
    const sectionId = normalizeText(rawSectionId);
    if (!sectionId) continue;
    map[sectionId] = key;
  }
  return map;
}

function sectionIdByKey(sectionIds = {}) {
  const map = {};
  for (const [key, rawSectionId] of Object.entries(sectionIds || {})) {
    const sectionId = normalizeText(rawSectionId);
    if (!sectionId) continue;
    map[key] = sectionId;
  }
  return map;
}

function buildFallbackContainerId(memberIds = [], index = 0) {
  const first = normalizeText(memberIds[0]) || "group";
  const safeFirst = first.replace(/[^a-zA-Z0-9_-]/g, "_");
  return `container_auto_${index}_${safeFirst}`;
}

export function createSectionContainerTargetKey(containerId) {
  const normalized = normalizeText(containerId);
  if (!normalized) return null;
  return `${SECTION_CONTAINER_TARGET_PREFIX}${normalized}`;
}

export function parseSectionContainerTargetKey(targetKey) {
  const value = String(targetKey || "");
  if (!value.startsWith(SECTION_CONTAINER_TARGET_PREFIX)) return null;
  return normalizeText(value.slice(SECTION_CONTAINER_TARGET_PREFIX.length));
}

export function isSectionContainerTargetKey(targetKey) {
  return parseSectionContainerTargetKey(targetKey) !== null;
}

export function buildSectionContainerMaps(order = [], sectionStructure = [], sectionIds = {}) {
  const orderedKeys = uniqueOrdered(Array.isArray(order) ? order : []);
  const validKeySet = new Set(orderedKeys);
  const keysById = keyBySectionId(sectionIds);
  const sectionToContainerId = {};
  const containersById = {};
  const usedContainerIds = new Set();
  const nodes = [];
  const containerMemberSetById = {};

  // Parse container membership from structure and clamp it to the provided flat order.
  const rawNodes = Array.isArray(sectionStructure) ? sectionStructure : [];
  for (const node of rawNodes) {
    if (!node || typeof node !== "object") continue;
    if (String(node.type || "").trim().toLowerCase() !== "container") continue;

    const memberIds = Array.isArray(node.section_ids) ? node.section_ids : [];
    const members = [];
    const memberSeen = new Set();
    for (const memberId of memberIds) {
      const key = keysById[normalizeText(memberId)];
      if (!key || !validKeySet.has(key) || memberSeen.has(key) || sectionToContainerId[key]) continue;
      memberSeen.add(key);
      members.push(key);
    }
    if (members.length < 2) continue;

    let resolvedContainerId = normalizeText(node.container_id) || buildFallbackContainerId(members, Object.keys(containersById).length);
    let dedupeIndex = 2;
    while (usedContainerIds.has(resolvedContainerId)) {
      resolvedContainerId = `${resolvedContainerId}_${dedupeIndex}`;
      dedupeIndex += 1;
    }
    usedContainerIds.add(resolvedContainerId);

    containersById[resolvedContainerId] = {
      id: resolvedContainerId,
      members: [...members],
    };
    containerMemberSetById[resolvedContainerId] = new Set(members);
    for (const key of members) {
      sectionToContainerId[key] = resolvedContainerId;
    }
  }

  // Emit nodes in flat order so non-grouped sections keep their canonical position.
  const emittedContainerIds = new Set();
  const flattenedKeys = [];
  for (const key of orderedKeys) {
    const containerId = sectionToContainerId[key];
    if (!containerId) {
      nodes.push({ type: "section", key });
      flattenedKeys.push(key);
      continue;
    }
    if (emittedContainerIds.has(containerId)) continue;

    const memberSet = containerMemberSetById[containerId];
    const members = orderedKeys.filter((orderedKey) => memberSet?.has(orderedKey));
    if (members.length < 2) {
      nodes.push({ type: "section", key });
      flattenedKeys.push(key);
      continue;
    }

    containersById[containerId] = { id: containerId, members };
    nodes.push({
      type: "container",
      containerId,
      members,
    });
    emittedContainerIds.add(containerId);
    for (const memberKey of members) {
      flattenedKeys.push(memberKey);
      sectionToContainerId[memberKey] = containerId;
    }
  }

  return {
    nodes,
    flattenedKeys,
    sectionToContainerId,
    containersById,
  };
}

export function deriveSectionOrderFromStructure(sectionStructure = [], sectionIds = {}, fallbackOrder = []) {
  const keysById = keyBySectionId(sectionIds);
  const validKeys = new Set(Object.keys(sectionIds || {}));
  const orderedKeys = [];
  const seen = new Set();

  for (const node of Array.isArray(sectionStructure) ? sectionStructure : []) {
    if (!node || typeof node !== "object") continue;
    const nodeType = String(node.type || "").trim().toLowerCase();
    if (nodeType === "section") {
      const key = keysById[normalizeText(node.section_id)];
      if (!key || seen.has(key) || !validKeys.has(key)) continue;
      seen.add(key);
      orderedKeys.push(key);
      continue;
    }
    if (nodeType !== "container") continue;
    const memberIds = Array.isArray(node.section_ids) ? node.section_ids : [];
    for (const memberId of memberIds) {
      const key = keysById[normalizeText(memberId)];
      if (!key || seen.has(key) || !validKeys.has(key)) continue;
      seen.add(key);
      orderedKeys.push(key);
    }
  }

  for (const key of uniqueOrdered(Array.isArray(fallbackOrder) ? fallbackOrder : [])) {
    if (!validKeys.has(key) || seen.has(key)) continue;
    seen.add(key);
    orderedKeys.push(key);
  }

  for (const key of Object.keys(sectionIds || {})) {
    if (!seen.has(key)) {
      seen.add(key);
      orderedKeys.push(key);
    }
  }

  return orderedKeys;
}

export function buildSectionStructureFromEntries(entries = [], sectionIds = {}, fallbackOrder = []) {
  const idsByKey = sectionIdByKey(sectionIds);
  const consumed = new Set();
  const structure = [];

  for (const entry of Array.isArray(entries) ? entries : []) {
    if (!entry || typeof entry !== "object") continue;
    if (entry.type === "container") {
      const containerId = normalizeText(entry.containerId);
      const members = [];
      for (const key of uniqueOrdered(entry.members || [])) {
        const sectionId = idsByKey[key];
        if (!sectionId || consumed.has(sectionId)) continue;
        consumed.add(sectionId);
        members.push(sectionId);
      }
      if (members.length >= 2) {
        const resolvedContainerId = containerId || buildFallbackContainerId(members, structure.length);
        structure.push({
          type: "container",
          container_id: resolvedContainerId,
          section_ids: members,
        });
      } else if (members.length === 1) {
        structure.push({
          type: "section",
          section_id: members[0],
        });
      }
      continue;
    }
    const sectionId = idsByKey[normalizeText(entry.key)];
    if (!sectionId || consumed.has(sectionId)) continue;
    consumed.add(sectionId);
    structure.push({
      type: "section",
      section_id: sectionId,
    });
  }

  for (const key of uniqueOrdered(Array.isArray(fallbackOrder) ? fallbackOrder : [])) {
    const sectionId = idsByKey[key];
    if (!sectionId || consumed.has(sectionId)) continue;
    consumed.add(sectionId);
    structure.push({
      type: "section",
      section_id: sectionId,
    });
  }

  return structure;
}

export function buildSectionStructureFromOrder(order = [], sectionIds = {}) {
  return buildSectionStructureFromEntries(
    uniqueOrdered(order).map((key) => ({ type: "section", key })),
    sectionIds,
    order,
  );
}

export function getContainerMembers(containerId, containerMaps) {
  const normalized = normalizeText(containerId);
  if (!normalized) return [];
  return containerMaps?.containersById?.[normalized]?.members || [];
}

export function getContainerLeaderKey(containerId, containerMaps) {
  return getContainerMembers(containerId, containerMaps)[0] || null;
}
