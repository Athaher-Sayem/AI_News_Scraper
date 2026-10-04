import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { fetchArticle, fetchArticles } from "../api.js";
import ArticleCard from "../components/ArticleCard.jsx";
import Thumbnail from "../components/Thumbnail.jsx";
import { ErrorNotice, Loading } from "../components/States.jsx";
import { formatDate, paragraphs, resolveSourceLink } from "../utils.js";

export default function ArticlePage() {
  const { id } = useParams();
  const [state, setState] = useState({ loading: true, error: null, article: null, related: [] });

  useEffect(() => {
    let active = true;
    setState({ loading: true, error: null, article: null, related: [] });
    async function load() {
      try {
        const article = await fetchArticle(id);
        let related = [];
        if (article.category) {
          const result = await fetchArticles({ category: article.category, page_size: 5 });
          related = result.items.filter((item) => item.id !== article.id).slice(0, 3);
        }
        if (active) setState({ loading: false, error: null, article, related });
      } catch (error) {
        if (active) setState({ loading: false, error: error.message, article: null, related: [] });
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [id]);

  if (state.loading) return <Loading label="Loading story…" />;
  if (state.error) return <ErrorNotice message={state.error} />;
  if (!state.article) return null;

  const { article, related } = state;
  const sourceLink = resolveSourceLink(article.url);

  return (
    <article className="story">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/">Home</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/section/${article.category}`}>{article.category}</Link>
      </nav>

      <p className="eyebrow">
        <span className="eyebrow__category">{article.category || "News"}</span>
        <span className="eyebrow__dot" aria-hidden="true">•</span>
        <time dateTime={article.scraped_date || undefined}>{formatDate(article.scraped_date)}</time>
      </p>
      <h1 className="story__headline">{article.title}</h1>
      <p className="story__byline">
        {article.source}
        {article.author ? ` · ${article.author}` : ""}
        {article.language ? ` · ${article.language}` : ""}
      </p>

      <figure className="story__figure">
        <Thumbnail article={article} className="thumb--story" />
      </figure>

      <p className="story__notice">
        Source excerpt · This is a collected source article, not an approved newspaper publication.
      </p>

      <div className="story__body">
        {paragraphs(article.content).map((text, index) => (
          <p key={index}>{text}</p>
        ))}
      </div>

      {sourceLink ? (
        <a className="source-link" href={sourceLink} rel="noopener noreferrer" target="_blank">
          Read the full story at {article.source} ↗
        </a>
      ) : (
        <p className="source-link source-link--missing">The original source link is unavailable.</p>
      )}

      {related.length ? (
        <section className="related">
          <h2>Related from {article.category}</h2>
          <div className="grid grid--three">
            {related.map((item) => (
              <div className="grid__item" key={item.id}>
                <Link to={`/article/${item.id}`}>
                  <Thumbnail article={item} className="thumb--grid" />
                </Link>
                <ArticleCard article={item} />
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </article>
  );
}
