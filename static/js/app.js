/* =========================================================================
   Home Maintenance Dashboard - single-page client
   No framework / no build step: plain ES modules-free JS so the Pi can run
   it straight from `git pull` with nothing to compile.
   ========================================================================= */

const PRIORITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };
const DIY_LABEL = { diy: "DIY", hire: "HIRE", either: "EITHER" };
const FREQ_LABEL = {
  weekly: "Weekly",
  twice_weekly: "Twice weekly",
  monthly: "Monthly",
  quarterly: "Quarterly",
  biannual: "Twice a year",
  annual: "Yearly",
  as_needed: "As needed",
};

const state = {
  today: null,        // Date (local midnight)
  tasks: [],
  history: [],
  view: "dashboard",
};

/* ---- Date helpers ------------------------------------------------------- */
function parseDate(iso) {
  // Treat YYYY-MM-DD as a local date (no timezone shift).
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}
function daysBetween(from, to) {
  const ms = to.setHours(0, 0, 0, 0) - new Date(from).setHours(0, 0, 0, 0);
  return Math.round(ms / 86400000);
}
function dueInfo(task) {
  // Returns {days, label, cls} where days = next_due - today (negative = overdue)
  if (!task.next_due) return { days: null, label: "No date set", cls: "normal" };
  const due = parseDate(task.next_due);
  const days = daysBetween(state.today, due);
  let label, cls;
  if (days < 0) { label = `Overdue by ${-days} day${-days === 1 ? "" : "s"}`; cls = "overdue"; }
  else if (days === 0) { label = "Due today"; cls = "soon"; }
  else if (days === 1) { label = "Due tomorrow"; cls = "soon"; }
  else if (days <= 7) { label = `Due in ${days} days`; cls = "soon"; }
  else { label = `Due in ${days} days`; cls = "normal"; }
  return { days, label, cls };
}
function fmtDate(iso) {
  const d = iso.length > 10 ? new Date(iso) : parseDate(iso);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
function fmtDateTime(iso) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
  });
}
function lastDone(taskId) {
  const entries = state.history.filter((h) => h.task_id === taskId);
  if (!entries.length) return null;
  return entries.reduce((a, b) => (a.completed_at > b.completed_at ? a : b)).completed_at;
}

/* ---- API ---------------------------------------------------------------- */
async function loadState() {
  const res = await fetch("/api/state");
  const data = await res.json();
  state.today = parseDate(data.today);
  state.tasks = data.tasks;
  state.history = data.history;
}
async function api(path, method = "POST", body = null) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : null,
  });
  return res.json();
}

/* ---- Small DOM helpers -------------------------------------------------- */
function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), 2200);
}

/* ---- Badges ------------------------------------------------------------- */
function badges(task) {
  let html = `<span class="badge prio-${task.priority}">${esc(task.priority)}</span>`;
  html += `<span class="badge ${task.diy_status}">${DIY_LABEL[task.diy_status]}</span>`;
  if (task.florida_specific) html += `<span class="badge fl">FL</span>`;
  return html;
}

/* ---- Task card ---------------------------------------------------------- */
function taskCard(task) {
  const info = dueInfo(task);
  const overdue = info.days !== null && info.days < 0;
  const card = el(`
    <div class="card prio-${task.priority} ${overdue ? "is-overdue" : ""}">
      <div class="card-body">
        <div class="card-title">${esc(task.name)}</div>
        <div class="card-meta">
          <span class="due ${info.cls}">${overdue ? "OVERDUE · " : ""}${esc(info.label)}</span>
          <span class="cat">${esc(task.category)}</span>
          ${badges(task)}
        </div>
      </div>
      <button class="card-complete" aria-label="Mark complete">
        <span class="check">&#10003;</span>Done
      </button>
    </div>`);
  card.querySelector(".card-body").addEventListener("click", () => openDetail(task.id));
  card.querySelector(".card-complete").addEventListener("click", (e) => {
    e.stopPropagation();
    completeTask(task.id);
  });
  return card;
}

/* ---- Sorting / grouping ------------------------------------------------- */
function sortByDueThenPriority(a, b) {
  const da = dueInfo(a).days, db = dueInfo(b).days;
  if (da !== db) return da - db;
  return PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority];
}
function activeDated() {
  return state.tasks.filter((t) => t.active && t.next_due);
}

/* ---- Views -------------------------------------------------------------- */
function renderDashboard(main) {
  document.getElementById("view-title").textContent = "Due Soon";
  const dated = activeDated();
  const week = dated.filter((t) => dueInfo(t).days <= 7).sort(sortByDueThenPriority);
  const month = dated
    .filter((t) => { const d = dueInfo(t).days; return d >= 8 && d <= 30; })
    .sort(sortByDueThenPriority);

  const overdue = week.filter((t) => dueInfo(t).days < 0);
  const thisWeek = week.filter((t) => dueInfo(t).days >= 0);

  if (overdue.length) {
    main.appendChild(sectionHead("Overdue", overdue.length, true));
    main.appendChild(cardList(overdue));
  }
  main.appendChild(sectionHead("Due this week", thisWeek.length));
  if (thisWeek.length) main.appendChild(cardList(thisWeek));
  else main.appendChild(el(`<div class="empty-note">Nothing else due in the next 7 days. ✅</div>`));

  main.appendChild(sectionHead("Due within 30 days", month.length));
  if (month.length) main.appendChild(cardList(month));
  else main.appendChild(el(`<div class="empty-note">Nothing due in 8–30 days.</div>`));
}

function renderUpcoming(main) {
  document.getElementById("view-title").textContent = "Upcoming (30+ days)";
  const upcoming = activeDated()
    .filter((t) => dueInfo(t).days > 30)
    .sort(sortByDueThenPriority);
  main.appendChild(sectionHead("Upcoming (more than 30 days out)", upcoming.length));
  if (upcoming.length) main.appendChild(cardList(upcoming));
  else main.appendChild(el(`<div class="empty-note">Nothing scheduled beyond 30 days.</div>`));
}

function renderHistory(main) {
  document.getElementById("view-title").textContent = "Completion Log";
  const names = Object.fromEntries(state.tasks.map((t) => [t.id, t.name]));
  const entries = [...state.history].sort((a, b) =>
    a.completed_at < b.completed_at ? 1 : -1);
  main.appendChild(sectionHead("Completed tasks", entries.length));
  if (!entries.length) {
    main.appendChild(el(`<div class="empty-note">No tasks completed yet.</div>`));
    return;
  }
  const wrap = el(`<div class="cards"></div>`);
  for (const h of entries) {
    wrap.appendChild(el(`
      <div class="log-row">
        <span class="log-name">${esc(names[h.task_id] || h.task_id)}</span>
        <span class="log-date">${esc(fmtDateTime(h.completed_at))}</span>
      </div>`));
  }
  main.appendChild(wrap);
}

function renderSettings(main) {
  document.getElementById("view-title").textContent = "Settings";

  // Group ALL tasks by category (active and inactive).
  const byCat = {};
  for (const t of [...state.tasks].sort((a, b) => a.name.localeCompare(b.name))) {
    (byCat[t.category] ||= []).push(t);
  }

  main.appendChild(el(`<div class="empty-note">
    Manage every task here — change DIY/Hire, priority, frequency, remove
    tasks from the plan, or trigger an as-needed task onto the dashboard.
  </div>`));

  for (const cat of Object.keys(byCat).sort()) {
    const block = el(`<div class="settings-cat"><h3>${esc(cat)}</h3></div>`);
    for (const t of byCat[cat]) block.appendChild(settingRow(t));
    main.appendChild(block);
  }
}

function settingRow(task) {
  const row = el(`
    <div class="setting-row ${task.active ? "" : "inactive"}">
      <span class="name">${esc(task.name)}${task.active ? "" : " (removed)"}</span>
      <div class="controls"></div>
    </div>`);
  const controls = row.querySelector(".controls");

  if (task.active) {
    controls.appendChild(selectField(task, "diy_status",
      { diy: "DIY", hire: "Hire", either: "Either" }));
    controls.appendChild(selectField(task, "priority",
      { critical: "Critical", high: "High", medium: "Medium", low: "Low" }));
    controls.appendChild(selectField(task, "frequency", FREQ_LABEL));

    // As-needed tasks that are not currently surfaced get a "Trigger" button.
    if (task.frequency === "as_needed" && !task.next_due) {
      const go = el(`<button class="small-btn go">Add to dashboard</button>`);
      go.addEventListener("click", async () => {
        await api(`/api/tasks/${task.id}/trigger`);
        await refresh();
        toast("Added to dashboard");
      });
      controls.appendChild(go);
    }

    const rm = el(`<button class="small-btn danger">Remove</button>`);
    rm.addEventListener("click", () => patchTask(task.id, { active: false }, "Removed from plan"));
    controls.appendChild(rm);
  } else {
    const restore = el(`<button class="small-btn go">Restore</button>`);
    restore.addEventListener("click", () => patchTask(task.id, { active: true }, "Restored"));
    controls.appendChild(restore);
  }
  return row;
}

function selectField(task, field, options) {
  const sel = el(`<select class="field" aria-label="${field}"></select>`);
  for (const [val, label] of Object.entries(options)) {
    const opt = document.createElement("option");
    opt.value = val;
    opt.textContent = label;
    if (task[field] === val) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.addEventListener("change", () => patchTask(task.id, { [field]: sel.value }, "Updated"));
  return sel;
}

/* ---- Shared render bits ------------------------------------------------- */
function sectionHead(label, count, overdue = false) {
  return el(`<div class="section-head ${overdue ? "overdue-head" : ""}">
    ${esc(label)}<span class="count">${count}</span></div>`);
}
function cardList(tasks) {
  const wrap = el(`<div class="cards"></div>`);
  for (const t of tasks) wrap.appendChild(taskCard(t));
  return wrap;
}

/* ---- Detail overlay ----------------------------------------------------- */
function openDetail(taskId) {
  const task = state.tasks.find((t) => t.id === taskId);
  if (!task) return;
  const info = dueInfo(task);
  const done = lastDone(taskId);
  const card = document.getElementById("overlay-card");

  card.innerHTML = `
    <div class="detail-head">
      <h2 class="detail-title">${esc(task.name)}</h2>
      <button class="btn close" id="detail-close" aria-label="Close">&times;</button>
    </div>
    <div class="detail-meta">${badges(task)}
      ${task.florida_specific ? "" : ""}</div>
    <div class="detail-desc">${esc(task.description)}</div>
    <div class="detail-row"><span class="label">Category</span><span>${esc(task.category)}</span></div>
    <div class="detail-row"><span class="label">Frequency</span><span>${esc(FREQ_LABEL[task.frequency] || task.frequency)}</span></div>
    <div class="detail-row"><span class="label">Next due</span><span class="due ${info.cls}">${task.next_due ? esc(fmtDate(task.next_due)) + " · " : ""}${esc(info.label)}</span></div>
    <div class="detail-row"><span class="label">Last done</span><span>${done ? esc(fmtDateTime(done)) : "Never recorded"}</span></div>
    <div class="detail-actions" id="detail-actions"></div>`;

  const actions = card.querySelector("#detail-actions");

  if (task.video_url) {
    const v = el(`<button class="btn video">▶ Watch how-to video</button>`);
    v.addEventListener("click", () => window.open(task.video_url, "_blank", "noopener"));
    actions.appendChild(v);
  }

  if (task.next_due) {
    const c = el(`<button class="btn primary">&#10003; Mark complete</button>`);
    c.addEventListener("click", () => { closeOverlay(); completeTask(task.id); });
    actions.appendChild(c);
  } else if (task.frequency === "as_needed") {
    const g = el(`<button class="btn primary">+ Add to dashboard</button>`);
    g.addEventListener("click", async () => {
      closeOverlay();
      await api(`/api/tasks/${task.id}/trigger`);
      await refresh();
      toast("Added to dashboard");
    });
    actions.appendChild(g);
  }

  card.querySelector("#detail-close").addEventListener("click", closeOverlay);
  document.getElementById("overlay").classList.remove("hidden");
}
function closeOverlay() {
  document.getElementById("overlay").classList.add("hidden");
}

/* ---- Mutations ---------------------------------------------------------- */
async function completeTask(taskId) {
  const task = state.tasks.find((t) => t.id === taskId);
  await api(`/api/tasks/${taskId}/complete`);
  await refresh();
  const updated = state.tasks.find((t) => t.id === taskId);
  if (task && task.frequency !== "as_needed" && updated && updated.next_due) {
    toast(`Done · next due ${fmtDate(updated.next_due)}`);
  } else {
    toast("Marked complete");
  }
}
async function patchTask(taskId, body, msg) {
  await api(`/api/tasks/${taskId}`, "PATCH", body);
  await refresh();
  toast(msg);
}

/* ---- Router / refresh --------------------------------------------------- */
function render() {
  const main = document.getElementById("main");
  main.innerHTML = "";
  main.scrollTop = 0;
  document.querySelectorAll(".navbtn").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === state.view));
  ({
    dashboard: renderDashboard,
    upcoming: renderUpcoming,
    history: renderHistory,
    settings: renderSettings,
  }[state.view] || renderDashboard)(main);
}
async function refresh() {
  await loadState();
  render();
}
function setView(view) {
  state.view = view;
  render();
}

/* ---- Boot --------------------------------------------------------------- */
document.querySelectorAll(".navbtn").forEach((b) =>
  b.addEventListener("click", () => setView(b.dataset.view)));
document.getElementById("overlay").addEventListener("click", (e) => {
  if (e.target.id === "overlay") closeOverlay();
});
document.getElementById("today-label").textContent = "";

(async function init() {
  await loadState();
  document.getElementById("today-label").textContent =
    state.today.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  render();
})();

// Refresh data when the day rolls over (kiosk runs 24/7) - re-fetch hourly.
setInterval(refresh, 60 * 60 * 1000);
