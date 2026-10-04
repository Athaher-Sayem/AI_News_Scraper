export function Loading({ label = "Loading stories…" }) {
  return <p className="state state--loading">{label}</p>;
}

export function ErrorNotice({ message }) {
  return (
    <div className="state state--error" role="alert">
      <strong>Something went wrong.</strong>
      <p>{message}</p>
    </div>
  );
}

export function EmptyState({ message = "No stories match this selection." }) {
  return <p className="state state--empty">{message}</p>;
}
