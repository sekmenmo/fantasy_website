(function () {
  const storageKey = "fantasy-dashboard-podcast-mode";
  const benchStorageKey = "fantasy-dashboard-bench-expanded";

  function applyPodcastMode(enabled) {
    document.body.classList.toggle("podcast-mode", enabled);
    document.querySelectorAll("[data-podcast-toggle]").forEach((toggle) => {
      toggle.checked = enabled;
    });
  }

  function savedPodcastMode() {
    return window.localStorage.getItem(storageKey) === "true";
  }

  function savedBenchExpanded() {
    const saved = window.localStorage.getItem(benchStorageKey);
    return saved === null ? true : saved === "true";
  }

  function applyBenchState(expanded) {
    document.querySelectorAll("[data-bench-grid]").forEach((bench) => {
      bench.hidden = !expanded;
    });
    document.querySelectorAll("[data-bench-toggle]").forEach((button) => {
      button.textContent = expanded ? "Collapse Bench" : "Expand Bench";
      button.setAttribute("aria-expanded", expanded ? "true" : "false");
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyPodcastMode(savedPodcastMode());
    applyBenchState(savedBenchExpanded());
  });

  document.addEventListener("change", (event) => {
    const target = event.target;
    if (target.matches("[data-podcast-toggle]")) {
      window.localStorage.setItem(storageKey, target.checked ? "true" : "false");
      applyPodcastMode(target.checked);
    }

    if (target.matches("[data-week-select]")) {
      const week = target.value;
      if (window.htmx) {
        window.htmx.ajax("GET", `/matchups/content?week=${week}&matchup=1`, {
          target: "#matchup-page-shell",
          swap: "innerHTML",
        });
        window.history.pushState({}, "", `/matchups?week=${week}&matchup=1`);
      } else {
        window.location.href = `/matchups?week=${week}&matchup=1`;
      }
    }
  });

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (target.matches("[data-bench-toggle]")) {
      const expanded = !savedBenchExpanded();
      window.localStorage.setItem(benchStorageKey, expanded ? "true" : "false");
      applyBenchState(expanded);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.target && ["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName)) {
      return;
    }
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
      return;
    }
    const switcher = document.querySelector(".matchup-switcher");
    if (!switcher || !window.htmx) {
      return;
    }
    const week = switcher.dataset.week;
    const current = Number.parseInt(switcher.dataset.matchup || "1", 10);
    const countText = document.querySelector(".matchup-counter strong")?.textContent || "1 of 1";
    const total = Number.parseInt(countText.split(" of ")[1] || "1", 10);
    const next = event.key === "ArrowRight"
      ? ((current % total) + 1)
      : (((current + total - 2) % total) + 1);
    window.htmx.ajax("GET", `/matchups/panel?week=${week}&matchup=${next}`, {
      target: "#matchup-panel-shell",
      swap: "innerHTML",
    });
    window.history.pushState({}, "", `/matchups?week=${week}&matchup=${next}`);
  });

  document.addEventListener("htmx:afterSwap", () => {
    applyPodcastMode(savedPodcastMode());
    applyBenchState(savedBenchExpanded());
  });

  document.addEventListener(
    "error",
    (event) => {
      const target = event.target;
      if (target.matches("img.player-photo")) {
        target.style.display = "none";
      }
      if (target.matches("img.team-avatar, img.table-avatar")) {
        const fallback = document.createElement("span");
        fallback.className = target.className + " avatar-fallback";
        fallback.textContent = "FB";
        target.replaceWith(fallback);
      }
    },
    true
  );
})();
