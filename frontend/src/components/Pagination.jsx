import { Link } from "react-router-dom";

// Build page links that preserve the current query string (used by the
// category and search listings).
export default function Pagination({ meta, basePath, query = {} }) {
  const page = Number(meta.page) || 1;
  const totalPages = Number(meta.total_pages) || 0;
  if (totalPages <= 1) return null;

  const search = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value) search.set(key, value);
  });

  const link = (target) => {
    const params = new URLSearchParams(search);
    params.set("page", String(target));
    return `${basePath}?${params.toString()}`;
  };

  return (
    <nav className="pagination" aria-label="Pages">
      {page > 1 ? <Link to={link(page - 1)}>← Previous</Link> : <span />}
      <span>
        Page {page} of {totalPages}
      </span>
      {page < totalPages ? <Link to={link(page + 1)}>Next →</Link> : <span />}
    </nav>
  );
}
