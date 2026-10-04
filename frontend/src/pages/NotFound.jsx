import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section className="state state--empty">
      <h1>Page not found</h1>
      <p>The page you were looking for is not here.</p>
      <Link to="/">Back to the front page</Link>
    </section>
  );
}
