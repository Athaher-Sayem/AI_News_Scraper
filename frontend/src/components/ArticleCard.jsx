import { Link } from "react-router-dom";

import { relativeTime } from "../utils.js";

// A compact story card: eyebrow (category · time), headline link, optional
// standfirst. Used in lists, grids and sidebars.
export default function ArticleCard({ article, lead = false, standfirst = null }) {
  return (
    <article className={`card ${lead ? "card--lead" : ""}`}>
      <p className="eyebrow">
        <span className="eyebrow__category">{article.category || "News"}</span>
        <span className="eyebrow__dot" aria-hidden="true">•</span>
        <time dateTime={article.scraped_date || undefined}>{relativeTime(article.scraped_date)}</time>
      </p>
      <h3 className="card__headline">
        <Link to={`/article/${article.id}`}>{article.title}</Link>
      </h3>
      {standfirst ? <p className="card__standfirst">{standfirst}</p> : null}
      <p className="card__source">{article.source}</p>
    </article>
  );
}
