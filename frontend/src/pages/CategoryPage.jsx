import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { fetchArticles } from "../api.js";
import { sectionBySlug } from "../sections.js";
import ArticleCard from "../components/ArticleCard.jsx";
import Pagination from "../components/Pagination.jsx";
import Thumbnail from "../components/Thumbnail.jsx";
import { EmptyState, ErrorNotice, Loading } from "../components/States.jsx";
import { excerpt } from "../utils.js";
import { useMeta } from "../useMeta.js";

const PAGE_SIZE = 12;

export default function CategoryPage() {
  const { slug } = useParams();
  const [searchParams] = useSearchParams();
  const page = searchParams.get("page") || "1";
  const section = sectionBySlug(slug);
  const [state, setState] = useState({ loading: true, error: null, items: [], meta: {} });
  useMeta(section?.label || "Section", section ? `Collected ${section.label} stories with source attribution.` : "");

  useEffect(() => {
    if (!section) return undefined;
    let active = true;
    setState({ loading: true, error: null, items: [], meta: {} });
    const params = { page, page_size: PAGE_SIZE };
    // "Latest" lists every collected story; named sections match any of their
    // category labels (e.g. both "sports" and "sport") via repeated params.
    if (section.categories.length) params.category = section.categories;
    fetchArticles(params)
      .then(({ items, meta }) => {
        if (active) setState({ loading: false, error: null, items, meta });
      })
      .catch((error) => {
        if (active) setState({ loading: false, error: error.message, items: [], meta: {} });
      });
    return () => {
      active = false;
    };
  }, [slug, page, section]);

  if (!section) return <EmptyState message="That section does not exist." />;
  if (state.loading) return <Loading />;
  if (state.error) return <ErrorNotice message={state.error} />;

  return (
    <section>
      <header className="page-head">
        <h1>{section.label}</h1>
        <span>{state.meta.total || 0} stories</span>
      </header>

      {state.items.length ? (
        <div className="listing">
          {state.items.map((article) => (
            <article className="listing__row" key={article.id}>
              <Thumbnail article={article} className="thumb--row" />
              <div>
                <ArticleCard article={article} />
                <p className="listing__excerpt">{excerpt(article.content, 32)}</p>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState message="No stories in this section yet." />
      )}

      <Pagination meta={state.meta} basePath={`/section/${slug}`} />
    </section>
  );
}
