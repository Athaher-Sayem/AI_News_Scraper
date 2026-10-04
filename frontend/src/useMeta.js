import { useEffect } from "react";

// Set the document title and description for the current route without pulling
// in a helmet dependency.
export function useMeta(title, description) {
  useEffect(() => {
    document.title = title ? `${title} · Newsroom` : "Newsroom";
    let tag = document.querySelector('meta[name="description"]');
    if (!tag) {
      tag = document.createElement("meta");
      tag.setAttribute("name", "description");
      document.head.appendChild(tag);
    }
    if (description) tag.setAttribute("content", description);
  }, [title, description]);
}
