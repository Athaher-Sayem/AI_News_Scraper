import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchArticles, fetchSection } from "../api.js";
import { SECTIONS } from "../sections.js";
import ArticleCard from "../components/ArticleCard.jsx";
import SectionBlock from "../components/SectionBlock.jsx";
import Thumbnail from "../components/Thumbnail.jsx";
import { ErrorNotice, Loading } from "../components/States.jsx";
import { excerpt, relativeTime } from "../utils.js";

export default function HomePage() {
  const [state, setState] = useState({ loading: true, error: null, top: [], sections: [], missed: [] });

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [top, missed, ...sectionResults] = await Promise.all([
          fetchArticles({ page_size: 9 }),
          fetchArticles({ page: 4, page_size: 6 }),
          ...SECTIONS.map((section) => fetchSection(section.categories, 6)),
        ]);
        if (!active) return;
        setState({
          loading: false,
          error: null,
          top: top.items,
          missed: missed.items,
          sections: SECTIONS.map((section, index) => ({ section, articles: sectionResults[index] }))
            .filter((entry) => entry.articles.length),
        });
      } catch (error) {
        if (active) setState((previous) => ({ ...previous, loading: false, error: error.message }));
      }
    }
    load();
    return () => {
      active = false;
    };
  }, []);

  if (state.loading) return <Loading />;
  if (state.error) return <ErrorNotice message={state.error} />;

  const [lead, ...rest] = state.top;

  return (
    <>
      {lead ? (
        <section className="hero" aria-label="Top story">
          <article className="hero__lead">
            <Link to={`/article/${lead.id}`} className="hero__media">
              <Thumbnail article={lead} className="thumb--hero" />
            </Link>
            <p className="eyebrow eyebrow--light">
              <span className="eyebrow__category">{lead.category || "News"}</span>
            </p>
            <h1 className="hero__headline">
              <Link to={`/article/${lead.id}`}>{lead.title}</Link>
            </h1>
            <p className="hero__standfirst">{excerpt(lead.content, 34)}</p>
          </article>

          <aside className="hero__side" aria-label="More top news">
            <h2 className="hero__side-title">Top News</h2>
            <ol className="toplist">
              {rest.slice(0, 8).map((article) => (
                <li key={article.id}>
                  <Link to={`/article/${article.id}`}>{article.title}</Link>
                  <span className="toplist__meta">
                    {relativeTime(article.scraped_date)} • {article.category}
                  </span>
                </li>
              ))}
            </ol>
          </aside>
        </section>
      ) : null}

      {state.sections.map(({ section, articles }) => (
        <SectionBlock key={section.slug} section={section} articles={articles} />
      ))}

      {state.missed.length ? (
        <section className="section section--missed">
          <header className="section__head">
            <h2>In Case You Missed It</h2>
            <Link className="section__more" to="/section/latest?page=4">More news</Link>
          </header>
          <div className="grid">
            {state.missed.map((article) => (
              <div className="grid__item" key={article.id}>
                <Link to={`/article/${article.id}`}>
                  <Thumbnail article={article} className="thumb--grid" />
                </Link>
                <ArticleCard article={article} />
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
