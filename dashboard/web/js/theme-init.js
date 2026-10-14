// Runs before first paint so the saved theme never flashes the wrong colors.
(function () {
  try {
    var saved = localStorage.getItem("console.theme");
    if (saved === "light" || saved === "dark") {
      document.documentElement.setAttribute("data-theme", saved);
    }
  } catch (error) { /* storage unavailable: follow the system theme */ }
})();
