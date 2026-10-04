import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { fetchArticles } from "../api.js";
import ArticleCard from "../components/ArticleCard.jsx";
import Pagination from "../components/Pagination.jsx";
import Thumbnail from "../components/Thumbnail.jsx";
import { EmptyState, ErrorNotice, Loading } from "../components/States.jsx";
import { excerpt } from "../utils.js";

const PAGE_SIZE = 12;

export default function SearchPage() {
  const [searchParams] = useSearchParams();
  const query = (searchParams.get("q") || "").trim();
  const page = searchParams.get("page") || "1";
  const [state, setState] = useState({ loading: false, error: null, items: [], meta: {} });

  useEffect(() => {
    if (!query) {
      setState({ loading: false, error: null, items: [], meta: {} });
      return undefined;
    }
    let active = true;
    setState({ loading: true, error: null, items: [], meta: {} });
    fetchArticles({ q: query, page, page_size: PAGE_SIZE })
      .then(({ items, meta }) => {
        if (active) setState({ loading: false, error: null, items, meta });
      })
      .catch((error) => {
        if (active) setState({ loading: false, error: error.message, items: [], meta: {} });
      });
    return () => {
      active = false;
    };
  }, [query, page]);

  if (!query) return <EmptyState message="Type a headline or topic above to search collected stories." />;
  if (state.loading) return <Loading label={`Searching for “${query}”…`} />;
  if (state.error) return <ErrorNotice message={state.error} />;

  return (
    <section>
      <header className="page-head">
        <h1>Search: “{query}”</h1>
        <span>{state.meta.total || 0} results</span>
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
        <EmptyState message="No stories match this search." />
      )}

      <Pagination meta={state.meta} basePath="/search" query={{ q: query }} />
    </section>
  );
}
