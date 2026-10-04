const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// The stored image path is sometimes absolute and sometimes relative to the
// publisher (for example "/sites/default/files/....jpg"). Resolve it against
// the article's own URL and reject anything that is not http(s).
export function resolveImage(imageUrl, articleUrl) {
  if (!imageUrl) return null;
  try {
    const resolved = new URL(imageUrl, articleUrl || window.location.origin);
    if (resolved.protocol !== "http:" && resolved.protocol !== "https:") return null;
    return resolved.toString();
  } catch {
    return null;
  }
}

// Only link to a publisher when the stored URL is a real http(s) address with a
// hostname; mirrors the server-side attribution guard.
export function resolveSourceLink(url) {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if ((parsed.protocol === "http:" || parsed.protocol === "https:") && parsed.hostname) {
      return parsed.toString();
    }
  } catch {
    return null;
  }
  return null;
}

export function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

export function relativeTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return formatDate(value);
  const minutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} MIN`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} HOUR${hours === 1 ? "" : "S"}`;
  return formatDate(value);
}

export function paragraphs(content) {
  if (!content) return [];
  return content
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);
}

export function excerpt(content, words = 30) {
  if (!content) return "";
  const parts = content.trim().split(/\s+/);
  if (parts.length <= words) return content.trim();
  return `${parts.slice(0, words).join(" ")}…`;
}
