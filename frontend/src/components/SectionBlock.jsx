import { Link } from "react-router-dom";

import ArticleCard from "./ArticleCard.jsx";
import Thumbnail from "./Thumbnail.jsx";
import { excerpt } from "../utils.js";

// One homepage section: a lead story with a picture plus a short list of the
// next stories, mirroring the reference newspaper's section blocks.
export default function SectionBlock({ section, articles }) {
  if (!articles.length) return null;
  const [lead, ...rest] = articles;

  return (
    <section className="section">
      <header className="section__head">
        <h2><Link to={`/section/${section.slug}`}>{section.label}</Link></h2>
        <Link className="section__more" to={`/section/${section.slug}`}>More {section.label}</Link>
      </header>
      <div className="section__body">
        <article className="lead">
          <Link to={`/article/${lead.id}`} className="lead__media">
            <Thumbnail article={lead} className="thumb--lead" />
          </Link>
          <h3 className="lead__headline">
            <Link to={`/article/${lead.id}`}>{lead.title}</Link>
          </h3>
          <p className="lead__standfirst">{excerpt(lead.content, 24)}</p>
        </article>
        <div className="section__list">
          {rest.slice(0, 4).map((article) => (
            <ArticleCard key={article.id} article={article} />
          ))}
        </div>
      </div>
    </section>
  );
}
