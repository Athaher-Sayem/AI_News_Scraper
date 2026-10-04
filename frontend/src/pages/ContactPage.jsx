import { useMeta } from "../useMeta.js";

export default function ContactPage() {
  useMeta("Contact", "Contact the Newsroom team about corrections, attribution, or access.");

  return (
    <article className="page-article">
      <h1>Contact</h1>
      <p>
        Found a broken link, a wrong attribution, or content that should not be listed?
        Get in touch and include the story link so we can correct it quickly.
      </p>
      <ul className="contact-list">
        <li><strong>Corrections and attribution</strong> — <a href="mailto:desk@example.com">desk@example.com</a></li>
        <li><strong>API and integrations</strong> — see the <a href="/api/v1/docs/">API documentation</a></li>
        <li><strong>Editorial access</strong> — sign in to the <a href="/admin/">editor admin</a></li>
      </ul>
    </article>
  );
}
