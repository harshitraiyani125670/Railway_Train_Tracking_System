// ---------------------------------------------------------------------
// Clock in the header (just a nice touch, matches the station-board feel)
// ---------------------------------------------------------------------
function updateClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  document.getElementById("clock").textContent = `${hh}:${mm}:${ss}`;
}
updateClock();
setInterval(updateClock, 1000);

// ---------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------
const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabButtons.forEach((b) => b.classList.remove("active"));
    tabPanels.forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`panel-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------------------------------------------------------------------
// Station name autocomplete (searches all 10,000+ Indian stations)
// ---------------------------------------------------------------------
function setupStationAutocomplete(inputId, datalistId) {
  const input = document.getElementById(inputId);
  const datalist = document.getElementById(datalistId);
  let debounceTimer = null;
  let latestRequestId = 0;      // guards against a slow, stale response overwriting a newer one
  const cache = new Map();      // remembers recent queries so re-typing/backspacing feels instant

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const query = input.value.trim();
    if (query.length < 2) {
      datalist.innerHTML = "";
      return;
    }

    if (cache.has(query)) {
      renderOptions(cache.get(query));
      return;
    }

    // Short debounce - just enough to avoid firing on every single keystroke
    // while typing fast, without feeling laggy.
    debounceTimer = setTimeout(() => fetchSuggestions(query), 120);
  });

  function renderOptions(results) {
    datalist.innerHTML = results.map((s) => `<option value="${escapeHtml(s.name)}">`).join("");
  }

  async function fetchSuggestions(query) {
    const requestId = ++latestRequestId;
    try {
      const resp = await fetch(`/api/stations/search?q=${encodeURIComponent(query)}`);
      const data = await resp.json();
      if (requestId !== latestRequestId) return; // a newer keystroke already superseded this
      const results = data.results || [];
      cache.set(query, results);
      renderOptions(results);
    } catch (err) {
      // Autocomplete failing silently is fine - search still works without it
    }
  }
}

setupStationAutocomplete("from-city", "from-suggestions");
setupStationAutocomplete("to-city", "to-suggestions");

// ---------------------------------------------------------------------
// Search Trains tab
// ---------------------------------------------------------------------
const searchForm = document.getElementById("search-form");
const searchBtn = document.getElementById("search-btn");
const searchStatus = document.getElementById("search-status");
const searchBoard = document.getElementById("search-board");

searchForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const from = document.getElementById("from-city").value.trim();
  const to = document.getElementById("to-city").value.trim();
  const date = document.getElementById("travel-date").value;

  if (!from || !to) return;

  setStatus(searchStatus, `Searching ${from} \u2192 ${to} ...`, "");
  searchBtn.disabled = true;
  clearBoardRows();

  try {
    const params = new URLSearchParams({ from, to });
    if (date) params.set("date", date);

    const resp = await fetch(`/api/trains?${params}`);
    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || "Something went wrong.");
    }

    renderTrains(data.trains, from, to);
  } catch (err) {
    setStatus(searchStatus, err.message, "error");
    showEmptyBoard("SEARCH FAILED \u2014 SEE MESSAGE ABOVE");
  } finally {
    searchBtn.disabled = false;
  }
});

function clearBoardRows() {
  document.querySelectorAll("#search-board .board-row:not(.board-head)").forEach((r) => r.remove());
  document.querySelectorAll("#search-board .board-empty").forEach((r) => r.remove());
}

function showEmptyBoard(message) {
  clearBoardRows();
  const div = document.createElement("div");
  div.className = "board-empty";
  div.textContent = message;
  searchBoard.appendChild(div);
}

function renderTrains(trains, from, to) {
  clearBoardRows();

  if (!trains || trains.length === 0) {
    setStatus(searchStatus, `No trains found between ${from} and ${to}.`, "error");
    showEmptyBoard("NO TRAINS FOUND");
    return;
  }

  trains.forEach((t, i) => {
    const row = document.createElement("div");
    row.className = "board-row";
    row.innerHTML = `
      <span class="col-no">${i + 1}</span>
      <span class="col-train">${escapeHtml(t.number)}</span>
      <span class="col-name">${escapeHtml(t.name)}</span>
      <span class="col-time">${escapeHtml(t.departure)}</span>
      <span class="col-time">${escapeHtml(t.arrival)}</span>
      <span class="col-days">${escapeHtml(t.days)}</span>
    `;
    row.addEventListener("click", () => openRoute(t.number));
    searchBoard.appendChild(row);
  });

  setStatus(searchStatus, `${trains.length} train(s) found from ${from} to ${to} \u2014 click a train to see its live route`, "success");
}

// ---------------------------------------------------------------------
// Route timeline view (opened by clicking a train row)
// ---------------------------------------------------------------------
const routePanel = document.getElementById("panel-route");
const routeStatus = document.getElementById("route-status");
const routeHeader = document.getElementById("route-header");
const timeline = document.getElementById("timeline");
const routeBackBtn = document.getElementById("route-back-btn");

async function openRoute(trainNumber) {
  tabButtons.forEach((b) => b.classList.remove("active"));
  tabPanels.forEach((p) => p.classList.remove("active"));
  routePanel.classList.add("active");

  setStatus(routeStatus, `Loading route for train ${trainNumber} ...`, "");
  routeHeader.innerHTML = "";
  timeline.innerHTML = "";

  try {
    const resp = await fetch(`/api/route/${encodeURIComponent(trainNumber)}`);
    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || "Something went wrong.");
    }

    renderRoute(data, routeHeader, timeline);
    setStatus(routeStatus, "Route loaded.", "success");
  } catch (err) {
    setStatus(routeStatus, err.message, "error");
  }
}

// Renders a train's full station-by-station timeline into the given
// header/timeline elements. Shared by both the "click a train" Route view
// and the Live Status tab, so both look and behave identically.
function renderRoute(data, headerEl, timelineEl) {
  const train = data.train || {};
  headerEl.innerHTML = `
    <p class="route-title">${escapeHtml(train.number || "?")} \u2014 ${escapeHtml(train.name || "Unknown")}</p>
    <div class="route-delay">DELAY: ${escapeHtml(train.delay || "-")}</div>
  `;

  const stations = data.stations || [];
  if (stations.length === 0) {
    timelineEl.innerHTML = `<div class="board-empty">NO ROUTE DATA AVAILABLE</div>`;
    return;
  }

  // Find the train's current position: the last station that has already
  // been reached (color !== "upcoming"). If none have been reached yet,
  // the train is still at the very first station (source).
  let currentIndex = 0;
  for (let i = 0; i < stations.length; i++) {
    if (stations[i].color !== "upcoming") currentIndex = i;
  }

  timelineEl.innerHTML = stations.map((s, i) => {
    const statusClass = s.color === "late" ? "tl-status-late" : (s.color === "ontime" ? "tl-status-ontime" : "");
    const times = s.actualArrival || s.actualDeparture
      ? `${escapeHtml(s.actualArrival || "-")} \u2192 ${escapeHtml(s.actualDeparture || "-")}`
      : `${escapeHtml(s.scheduledArrival || "-")} \u2192 ${escapeHtml(s.scheduledDeparture || "-")} (scheduled)`;
    const isCurrent = i === currentIndex;

    return `
      <div class="tl-station${isCurrent ? " tl-current" : ""}" ${isCurrent ? 'data-current-marker="true"' : ""}>
        <span class="tl-dot ${s.color}${isCurrent ? " tl-dot-current" : ""}"></span>
        ${isCurrent ? '<span class="tl-here-badge">TRAIN IS HERE</span>' : ""}
        <span class="tl-code">${escapeHtml(s.code)}</span>
        <span class="tl-distance">${escapeHtml(s.distance)} km</span>
        <p class="tl-name">${escapeHtml(s.name)}</p>
        <p class="tl-meta">${times} &middot; Platform ${escapeHtml(s.platform)} ${s.statusText ? `&middot; <span class="${statusClass}">${escapeHtml(s.statusText)}</span>` : ""}</p>
      </div>
    `;
  }).join("");

  // Auto-scroll so the current position is immediately visible, instead of
  // making the user scroll down from the very first station every time.
  // Scoped to this specific container (via querySelector, not a global ID)
  // so the Search-results Route view and the Live Status tab never clash.
  const marker = timelineEl.querySelector('[data-current-marker="true"]');
  if (marker) {
    requestAnimationFrame(() => {
      setTimeout(() => {
        marker.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 60);
    });
  }
}

routeBackBtn.addEventListener("click", () => {
  routePanel.classList.remove("active");
  document.querySelector('.tab-btn[data-tab="search"]').classList.add("active");
  document.getElementById("panel-search").classList.add("active");
});

// ---------------------------------------------------------------------
// Live Status tab - shows the same full timeline as the Route view
// ---------------------------------------------------------------------
const liveForm = document.getElementById("live-form");
const liveBtn = document.getElementById("live-btn");
const liveStatus = document.getElementById("live-status");
const liveHeader = document.getElementById("live-header");
const liveTimeline = document.getElementById("live-timeline");

liveForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const trainNumber = document.getElementById("train-number").value.trim();
  if (!trainNumber) return;

  setStatus(liveStatus, `Tracking train ${trainNumber} ...`, "");
  liveBtn.disabled = true;
  liveHeader.innerHTML = "";
  liveTimeline.innerHTML = "";

  try {
    const resp = await fetch(`/api/route/${encodeURIComponent(trainNumber)}`);
    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || "Something went wrong.");
    }

    renderRoute(data, liveHeader, liveTimeline);
    setStatus(liveStatus, "Live data updated.", "success");
  } catch (err) {
    setStatus(liveStatus, err.message, "error");
    liveTimeline.innerHTML = `<div class="board-empty">TRACKING FAILED \u2014 SEE MESSAGE ABOVE</div>`;
  } finally {
    liveBtn.disabled = false;
  }
});

// ---------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------
function setStatus(el, text, kind) {
  el.textContent = text;
  el.className = "status-line" + (kind ? " " + kind : "");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}
