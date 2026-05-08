/**
 * Surface-local formatting helpers. Kept local to /settings/profiles
 * because nothing else needs them yet; promote to lib/utils when a
 * second caller appears.
 */

const SECONDS = {
  minute: 60,
  hour: 60 * 60,
  day: 60 * 60 * 24,
  week: 60 * 60 * 24 * 7,
  month: 60 * 60 * 24 * 30,
  year: 60 * 60 * 24 * 365,
};

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const diff = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (diff < 45) return "just now";
  if (diff < SECONDS.hour) return `${Math.round(diff / SECONDS.minute)}m ago`;
  if (diff < SECONDS.day) return `${Math.round(diff / SECONDS.hour)}h ago`;
  if (diff < SECONDS.week) return `${Math.round(diff / SECONDS.day)}d ago`;
  if (diff < SECONDS.month) return `${Math.round(diff / SECONDS.week)}w ago`;
  if (diff < SECONDS.year) return `${Math.round(diff / SECONDS.month)}mo ago`;
  return `${Math.round(diff / SECONDS.year)}y ago`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  return new Date(t).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
