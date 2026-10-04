import { useMeta } from "../useMeta.js";

export default function AboutPage() {
  useMeta("About", "About the Newsroom collected-news platform and how it attributes sources.");

  return (
    <article className="page-article">
      <h1>About</h1>
      <p>
        Newsroom is a collection desk. It gathers headlines, excerpts, and links from
        several Bangladeshi news publishers and presents them together so you can follow
        a story across sources. Every item stays attributed to the publisher that
        reported it.
      </p>
      <p>
        This view shows collected source material for review. It does not republish whole
        articles and it does not imply editorial approval. The full story always opens on
        the original publisher's site.
      </p>
      <p>
        The platform is built with a Django JSON API and a React front end. An AI
        processing pipeline (deduplication, fact extraction, generation, and verification)
        is under development and is not part of what is shown here.
      </p>
    </article>
  );
}
