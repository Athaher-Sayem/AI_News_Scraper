import { useState } from "react";

import { resolveImage } from "../utils.js";

// Publisher images can be relative paths or block hotlinking. Try the resolved
// URL, then fall back to a labelled block instead of a broken image.
export default function Thumbnail({ article, className = "" }) {
  const [failed, setFailed] = useState(false);
  const src = resolveImage(article.image_url, article.url);

  if (!src || failed) {
    return (
      <div className={`thumb thumb--fallback ${className}`} aria-hidden="true">
        <span>{(article.category || "News").toUpperCase()}</span>
      </div>
    );
  }

  return (
    <img
      className={`thumb ${className}`}
      src={src}
      alt={article.title}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}
