export function getButtonTypeClassName(typeId) {
  if (!typeId || typeId === "primary") return "";
  if (typeId === "secondary") return "secondary";
  if (typeId === "ghost") return "ghost";
  return String(typeId);
}

export function getButtonTypeClassMap(typeId) {
  const className = getButtonTypeClassName(typeId);
  if (!className) return {};
  return { [className]: true };
}

export function getButtonTypeInlineStyle(typeId) {
  if (!typeId || typeId === "primary" || typeId === "secondary" || typeId === "ghost") {
    return {};
  }
  return {
    '--btn-bg': `var(--button-${typeId}-bg-color, var(--button-bg-color, var(--accent)))`,
    '--btn-color': `var(--button-${typeId}-color, var(--button-color, #fff))`,
    '--btn-border-color': `var(--button-${typeId}-border-color, var(--button-border-color, transparent))`,
    '--btn-hover-bg': `var(--button-${typeId}-hover-bg-color, var(--button-hover-bg-color, var(--button-${typeId}-bg-color, var(--button-bg-color, var(--accent)))))`,
    '--btn-hover-color': `var(--button-${typeId}-hover-color, var(--button-hover-color, var(--button-${typeId}-color, var(--button-color, #fff))))`,
    '--btn-hover-border-color': `var(--button-${typeId}-hover-border-color, var(--button-hover-border-color, var(--button-${typeId}-border-color, var(--button-border-color, transparent))))`,
    fontSize: `var(--button-${typeId}-font-size, var(--button-font-size, 16px))`,
  };
}
