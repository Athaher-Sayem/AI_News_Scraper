// Navigation sections. Categories come straight from the collected data, which
// carries a few duplicate labels (sport/sports, latest/latest-news); each
// section lists every label it should merge, newest first.
export const SECTIONS = [
  { slug: "business", label: "Business", categories: ["business", "economy"] },
  { slug: "opinion", label: "Opinion", categories: ["opinion"] },
  { slug: "sports", label: "Sports", categories: ["sports", "sport"] },
  { slug: "culture", label: "Culture", categories: ["culture"] },
  { slug: "lifestyle", label: "Lifestyle", categories: ["lifestyle"] },
  { slug: "world", label: "World", categories: ["world"] },
];

export const NAV_ITEMS = [{ slug: "latest", label: "Latest", categories: [] }, ...SECTIONS];

export function sectionBySlug(slug) {
  return NAV_ITEMS.find((section) => section.slug === slug) || null;
}
