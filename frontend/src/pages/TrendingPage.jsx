import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchTrending } from "../api.js";
import ArticleCard from "../components/ArticleCard.jsx";
import Thumbnail from "../components/Thumbnail.jsx";
import { EmptyState, ErrorNotice, Loading } from "../components/States.jsx";
import { excerpt } from "../utils.js";
import { useMeta } from "../useMeta.js";

export default function TrendingPage() {
  useMeta("Trending", "The most-read collected stories over the last week.");
  const [state, setState] = useState({ loading: true, error: null, items: [] });

  useEffect(() => {
    let active = true;
    fetchTrending()
      .then((items) => {
        if (active) setState({ loading: false, error: null, items });
      })
      .catch((error) => {
        if (active) setState({ loading: false, error: error.message, items: [] });
      });
    return () => {
      active = false;
    };
  }, []);

  if (state.loading) return <Loading label="Loading trending…" />;
  if (state.error) return <ErrorNotice message={state.error} />;

  return (
    <section>
      <header className="page-head">
        <h1>Trending</h1>
        <span>Most read this week</span>
      </header>
      {state.items.length ? (
        <ol className="trending">
          {state.items.map((article, index) => (
            <li className="trending__row" key={article.id}>
              <span className="trending__rank">{index + 1}</span>
              <Link to={`/article/${article.id}`} className="trending__media">
                <Thumbnail article={article} className="thumb--row" />
              </Link>
              <div className="trending__body">
                <ArticleCard article={article} />
                <p className="listing__excerpt">{excerpt(article.content, 28)}</p>
                {article.views ? (
                  <p className="trending__views">{article.views} view{article.views === 1 ? "" : "s"}</p>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState message="No trending stories yet." />
      )}
    </section>
  );
}
