/* Vortex Agent — Mission Control App */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];

  const state = {
    view: "home",
    meta: null,
    bots: [],
    tools: [],
    seats: [],
    missions: [],
    councils: [],
    ws: null,
    wsRetries: 0,
    activeId: null,
    mode: null, // mission | council
  };

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    if (!res.ok) throw new Error((await res.text()) || res.statusText);
    const ct = res.headers.get("content-type") || "";
    return ct.includes("application/json") ? res.json() : res.text();
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ── navigation ──────────────────────────────────────────────────────────
  const TITLES = {
    home: ["Home", "Autonomous multi-agent OS · council chamber"],
    chat: ["Chat", "Talk to the chief · auto-routes complex goals"],
    missions: ["Missions", "Solo autonomous runs · live trace"],
    council: ["Council", "24 seats · vote · chamber workers"],
    seats: ["Seats", "Council personas + swarm bots"],
    tools: ["Tools", "Self-registering tool belt"],
    workspace: ["Workspace", "Artifacts under ~/.vortex/workspace"],
    settings: ["Settings", "Runtime identity and configuration"],
  };

  function showView(name) {
    state.view = name;
    $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
    $$(".nav-item").forEach((b) =>
      b.classList.toggle("active", b.dataset.view === name)
    );
    const [t, tag] = TITLES[name] || [name, ""];
    $("#view-title").textContent = t;
    $("#view-tag").textContent = tag;
    if (name === "missions") refreshMissions();
    if (name === "council") refreshCouncils();
    if (name === "workspace") refreshWorkspace();
    if (name === "settings") renderSettings();
  }

  // ── boot ────────────────────────────────────────────────────────────────
  async function boot() {
    bindNav();
    bindHome();
    bindChat();
    bindMissions();
    bindCouncil();
    await refreshMeta();
    await Promise.all([refreshMissions(), refreshCouncils(), refreshStats()]);
    connectWs();
  }

  function bindNav() {
    $$(".nav-item").forEach((btn) =>
      btn.addEventListener("click", () => showView(btn.dataset.view))
    );
    $$("[data-goto]").forEach((btn) =>
      btn.addEventListener("click", () => showView(btn.dataset.goto))
    );
  }

  async function refreshMeta() {
    try {
      const [health, meta] = await Promise.all([api("/health"), api("/api/meta")]);
      state.meta = meta;
      state.bots = meta.bots || [];
      state.tools = meta.tools || [];
      state.seats = meta.council_seats || [];
      setPill("pill-health", "ok", `online · v${health.version || meta.version}`);
      setPill("pill-provider", "dim", `brain: ${meta.provider || "offline"}`);
      setPill("pill-bots", "dim", `bots: ${(meta.bots || []).length}`);
      setPill("pill-seats", "dim", `seats: ${(meta.council_seats || []).length}`);
      $("#nav-version").textContent = `v${meta.version || "—"}`;
      renderBots();
      renderTools();
      renderSeats();
      renderHomeSeats();
      renderSettings();
    } catch (e) {
      setPill("pill-health", "bad", "offline");
      console.warn(e);
    }
  }

  async function refreshStats() {
    try {
      const s = await api("/api/stats");
      const items = [
        ["Messages", s.messages ?? 0],
        ["Sessions", s.sessions ?? s.missions ?? 0],
        ["Steps", s.steps ?? s.tool_calls ?? 0],
        ["Tools", s.tools ?? state.tools.length],
      ];
      $("#home-stats").innerHTML = items
        .map(
          ([k, v]) =>
            `<div class="stat"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`
        )
        .join("");
    } catch (_) {}
  }

  function setPill(id, cls, text) {
    const el = $("#" + id);
    if (!el) return;
    el.className = "pill " + (cls === "dim" ? "dim" : cls);
    el.innerHTML = (cls === "dim" ? "" : "<i></i>") + text;
  }

  // ── renderers ───────────────────────────────────────────────────────────
  function renderBots() {
    const icons = {
      orchestrator: "🧠",
      research: "🔍",
      coding: "🏗️",
      security: "🔒",
      scout: "🛰️",
    };
    $("#bot-list").innerHTML = state.bots
      .map(
        (b) => `
      <li>
        <div class="bot-avatar">${icons[b.role] || "🤖"}</div>
        <div class="bot-meta">
          <div class="name">${esc(b.name)}</div>
          <div class="role">${esc(b.role)} · ${esc(b.toolset || "")} · ${b.messages || 0} msgs</div>
        </div>
      </li>`
      )
      .join("");
  }

  function renderTools() {
    $("#tool-count").textContent = String(state.tools.length);
    $("#tool-list").innerHTML = state.tools
      .map(
        (t) => `
      <li>
        <div class="name">${esc(t.name)}</div>
        <div class="desc">${esc(t.description || "")}</div>
      </li>`
      )
      .join("");
  }

  function seatCard(s) {
    return `
      <div class="seat-card" title="${esc(s.mandate || "")}">
        <div class="top">
          <div class="bot-avatar" style="background:linear-gradient(135deg,${esc(
            s.color || "#f97316"
          )}55,rgba(34,211,238,0.12))">${esc(s.icon || "◆")}</div>
          <div>
            <div class="name">${esc(s.name)}</div>
            <div class="project">${esc(s.project || s.title || "")}</div>
          </div>
        </div>
        <div class="mandate">${esc((s.mandate || "").slice(0, 120))}</div>
      </div>`;
  }

  function renderSeats() {
    $("#seat-count").textContent = String(state.seats.length);
    $("#seat-grid").innerHTML = state.seats.map(seatCard).join("");
  }

  function renderHomeSeats() {
    $("#home-seats").innerHTML = state.seats.slice(0, 8).map(seatCard).join("");
  }

  function renderSettings() {
    const m = state.meta || {};
    const rows = [
      ["Product", m.name || "Vortex Agent"],
      ["Version", m.version || "—"],
      ["Brain", m.provider || "offline"],
      ["Model", m.model || "offline-planner"],
      ["Architecture", m.architecture || "—"],
      ["Chamber", m.chamber ? "enabled" : "off"],
      ["Workspace", m.workspace || "~/.vortex/workspace"],
      ["Seats", String((m.council_seats || state.seats).length)],
      ["Tools", String((m.tools || state.tools).length)],
      ["Bots", String((m.bots || state.bots).length)],
    ];
    $("#settings-grid").innerHTML = rows
      .map(
        ([k, v]) =>
          `<div class="row"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`
      )
      .join("");
  }

  function renderMissionList(el, items, onClick) {
    if (!items.length) {
      el.innerHTML = `<li class="muted" style="border:none;background:transparent">None yet</li>`;
      return;
    }
    el.innerHTML = items
      .slice(0, 25)
      .map((m) => {
        const active = m.id === state.activeId ? "active" : "";
        return `
        <li class="${active}" data-id="${esc(m.id)}">
          <div class="mission-meta" style="width:100%">
            <div style="display:flex;justify-content:space-between;gap:8px;align-items:center">
              <div class="name">${esc(m.id)}</div>
              <span class="badge ${esc(m.status)}">${esc(m.status)}</span>
            </div>
            <div class="sub">${esc((m.goal || m.title || "").slice(0, 80))}</div>
            <div class="sub">${m.step_count || m.opinion_count || 0} steps/opinions</div>
          </div>
        </li>`;
      })
      .join("");
    el.querySelectorAll("li[data-id]").forEach((li) =>
      li.addEventListener("click", () => onClick(li.dataset.id))
    );
  }

  async function refreshMissions() {
    try {
      state.missions = await api("/api/missions");
      renderMissionList($("#mission-list"), state.missions, loadMission);
      renderMissionList($("#home-missions"), state.missions, (id) => {
        showView("missions");
        loadMission(id);
      });
    } catch (_) {}
  }

  async function refreshCouncils() {
    try {
      state.councils = await api("/api/council");
      renderMissionList($("#council-list"), state.councils, loadCouncil);
    } catch (_) {}
  }

  async function refreshWorkspace() {
    const m = state.meta || {};
    $("#workspace-path").textContent = m.workspace || "~/.vortex/workspace";
    // best-effort: list recent council finals from mission/council APIs
    const lines = [];
    lines.push("Workspace root: " + (m.workspace || "~/.vortex/workspace"));
    lines.push("");
    lines.push("Recent council sessions:");
    for (const c of (state.councils || []).slice(0, 8)) {
      const ex = c.execution || c.chamber || {};
      lines.push(
        `• ${c.id} [${c.status}] ${ex.final_path || ex.chamber_dir || c.goal || ""}`.slice(
          0,
          120
        )
      );
    }
    lines.push("");
    lines.push("Recent missions:");
    for (const x of (state.missions || []).slice(0, 8)) {
      lines.push(`• ${x.id} [${x.status}] ${(x.goal || "").slice(0, 60)}`);
    }
    lines.push("");
    lines.push("Tip: open council/<id>/FINAL.md on the host for full verdicts.");
    $("#workspace-body").textContent = lines.join("\n");
  }

  // ── websocket ───────────────────────────────────────────────────────────
  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    try {
      state.ws = new WebSocket(`${proto}://${location.host}/ws`);
    } catch (_) {
      scheduleReconnect();
      return;
    }
    state.ws.onopen = () => {
      state.wsRetries = 0;
      setPill("pill-ws", "ok", "ws: live");
      $("#footer-ws").textContent = "realtime connected";
    };
    state.ws.onclose = () => {
      setPill("pill-ws", "bad", "ws: off");
      $("#footer-ws").textContent = "realtime offline";
      scheduleReconnect();
    };
    state.ws.onerror = () => state.ws.close();
    state.ws.onmessage = (ev) => {
      try {
        handleEvent(JSON.parse(ev.data));
      } catch (_) {}
    };
  }

  function scheduleReconnect() {
    state.wsRetries += 1;
    const delay = Math.min(1000 * 2 ** Math.min(state.wsRetries, 5), 15000);
    setTimeout(connectWs, delay);
  }

  function handleEvent(ev) {
    if (!ev || !ev.type || ["hello", "ping", "pong"].includes(ev.type)) return;
    const mid = ev.mission_id || ev.session_id || ev.council_id;
    if (mid && !state.activeId) {
      state.activeId = mid;
      state.mode = String(ev.type).includes("council") || String(ev.type).includes("chamber")
        ? "council"
        : "mission";
    }
    if (mid && state.activeId && mid !== state.activeId) {
      if (String(ev.type).startsWith("mission_") || String(ev.type).startsWith("council_")) {
        refreshMissions();
        refreshCouncils();
      }
      return;
    }

    // home mini status
    if (["thought", "tool_call", "chamber_dispatch", "council_round"].includes(ev.type)) {
      $("#home-status").textContent =
        ev.thought ||
        ev.message ||
        `${ev.type}${ev.tool ? ": " + ev.tool : ""}${ev.round ? " · " + ev.round : ""}`;
      pushMini(
        ev.thought ||
          ev.message ||
          `${ev.type} ${ev.tool || ev.seat_name || ev.round || ""}`
      );
    }

    const traceId =
      state.mode === "council" ? "council-trace" : "trace";
    paintEvent(ev, traceId);

    if (["mission_completed", "council_completed"].includes(ev.type)) {
      if (ev.result) {
        if (state.mode === "council") showCouncilResult(ev.result);
        else showResult(ev.result);
      }
      $("#btn-cancel").disabled = true;
      $("#btn-council-cancel").disabled = true;
      $("#btn-launch").disabled = false;
      $("#btn-launch-council").disabled = false;
      $("#btn-council").disabled = false;
      $("#btn-home-solo").disabled = false;
      $("#btn-home-council").disabled = false;
      refreshMissions();
      refreshCouncils();
      refreshStats();
    }
    if (["mission_failed", "council_failed", "mission_cancelled", "council_cancelled"].includes(ev.type)) {
      $("#btn-cancel").disabled = true;
      $("#btn-council-cancel").disabled = true;
      $("#btn-launch").disabled = false;
      $("#btn-launch-council").disabled = false;
      $("#btn-council").disabled = false;
      refreshMissions();
      refreshCouncils();
    }
    if (ev.type === "council_consensus" && ev.tally) {
      const bar = $("#tally-bar");
      bar.hidden = false;
      bar.innerHTML = Object.entries(ev.tally)
        .map(
          ([k, v]) =>
            `<span class="chip ${esc(k)}">${esc(k)}: ${esc(
              typeof v === "number" ? v.toFixed(1) : v
            )}</span>`
        )
        .join("");
    }
  }

  function pushMini(text) {
    const box = $("#home-trace");
    const div = document.createElement("div");
    div.className = "line";
    div.textContent = String(text || "").slice(0, 140);
    box.prepend(div);
    while (box.children.length > 8) box.lastChild.remove();
  }

  function paintEvent(ev, traceId) {
    const map = {
      mission_queued: () =>
        appendStep(traceId, "system", "0", `Queued: ${ev.goal || ""}`),
      mission_started: () =>
        appendStep(traceId, "system", "0", `Started: ${ev.goal || ""}`),
      council_queued: () =>
        appendStep(traceId, "system", "0", `Council queued: ${ev.goal || ""}`),
      council_started: () =>
        appendStep(traceId, "system", "0", `Council seated`),
      council_round: () =>
        appendStep(
          traceId,
          "system",
          ev.round || "·",
          `Round: ${ev.round} — ${ev.message || ""}`
        ),
      council_opinion: () =>
        appendStep(
          traceId,
          "thought",
          ev.step || "·",
          `${ev.seat_name || ev.seat}${ev.project ? " · " + ev.project : ""} · ${ev.round}: ${ev.summary || ""}`,
          ev.stance
            ? `stance=${ev.stance}${ev.vote ? " vote=" + ev.vote : ""}`
            : ""
        ),
      council_consensus: () =>
        appendStep(
          traceId,
          "done",
          "⚖",
          `Consensus: ${(ev.winner || "").toUpperCase()}`,
          ev.tally ? JSON.stringify(ev.tally) : ""
        ),
      council_executing: () =>
        appendStep(traceId, "tool", "⚡", "Chamber + chief executing"),
      chamber_dispatch: () =>
        appendStep(
          traceId,
          "system",
          "⚡",
          ev.message || "Dispatching workers",
          (ev.workers || []).map((w) => w.name || w.seat).join(", ")
        ),
      chamber_worker_start: () =>
        appendStep(
          traceId,
          "tool",
          "⚙",
          `${ev.seat_name || ev.seat} started`,
          (ev.sub_goal || "").slice(0, 100)
        ),
      chamber_worker_done: () =>
        appendStep(
          traceId,
          ev.status === "completed" ? "obs" : "obs err",
          "✓",
          `${ev.seat_name || ev.seat}: ${ev.status}` +
            (ev.artifact ? ` · ${ev.artifact}` : "")
        ),
      chamber_merge: () =>
        appendStep(traceId, "system", "📎", ev.message || "Merging outputs"),
      thought: () =>
        appendStep(
          traceId,
          "thought",
          ev.step || "·",
          ev.thought || "(planning)",
          ev.action ? `→ ${ev.action}` : ""
        ),
      tool_call: () =>
        appendStep(
          traceId,
          "tool",
          ev.step || "·",
          `🔧 ${ev.tool}`,
          ev.args ? JSON.stringify(ev.args) : ""
        ),
      observation: () =>
        appendStep(
          traceId,
          ev.status === "success" ? "obs" : "obs err",
          ev.step || "·",
          ev.observation || ""
        ),
      mission_completed: () =>
        appendStep(traceId, "done", "✓", "Mission completed"),
      council_completed: () =>
        appendStep(traceId, "done", "⚖", "Council completed"),
      mission_failed: () =>
        appendStep(traceId, "obs err", "✗", `Failed: ${ev.error || ""}`),
      mission_cancelled: () =>
        appendStep(traceId, "system", "–", "Cancelled"),
    };
    if (map[ev.type]) {
      clearTraceEmpty(traceId);
      map[ev.type]();
    }
  }

  function clearTraceEmpty(id) {
    const empty = $(`#${id} .trace-empty`);
    if (empty) empty.remove();
  }

  function resetTrace(id) {
    $(`#${id}`).innerHTML = "";
  }

  function appendStep(traceId, kind, idx, body, args) {
    const trace = $("#" + traceId);
    if (!trace) return;
    const el = document.createElement("div");
    el.className = "step";
    const base = kind.replace(" err", "");
    el.innerHTML = `
      <div class="idx">#${esc(String(idx))}</div>
      <div>
        <span class="kind ${esc(base)}${kind.includes("err") ? " err" : ""}">${esc(
      base
    )}</span>
        <div class="body">${esc(body)}${
      args ? `<div class="args">${esc(args)}</div>` : ""
    }</div>
      </div>`;
    if (kind === "done") el.querySelector(".kind").className = "kind done";
    if (kind.includes("err")) el.querySelector(".kind").classList.add("err");
    trace.appendChild(el);
    trace.scrollTop = trace.scrollHeight;
  }

  function showResult(text) {
    $("#result-panel").hidden = false;
    $("#result-body").textContent = text || "(empty)";
  }
  function showCouncilResult(text) {
    $("#council-result-panel").hidden = false;
    $("#council-result-body").textContent = text || "(empty)";
  }

  // ── home ────────────────────────────────────────────────────────────────
  function bindHome() {
    $("#home-chips").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-goal]");
      if (b) $("#home-goal").value = b.dataset.goal;
    });
    $("#btn-home-chat").addEventListener("click", () => showView("chat"));
    $("#btn-home-solo").addEventListener("click", () => {
      const g = $("#home-goal").value.trim();
      if (!g) return $("#home-goal").focus();
      $("#mission-goal").value = g;
      showView("missions");
      launchMission();
    });
    $("#btn-home-council").addEventListener("click", () => {
      const g = $("#home-goal").value.trim();
      if (!g) return $("#home-goal").focus();
      $("#council-goal").value = g;
      showView("council");
      launchCouncil();
    });
  }

  // ── chat ────────────────────────────────────────────────────────────────
  function bindChat() {
    $("#chat-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const v = $("#chat-input").value.trim();
      if (!v) return;
      $("#chat-input").value = "";
      await sendChat(v);
    });
    $("#chat-chips").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-msg]");
      if (b) sendChat(b.dataset.msg);
    });
  }

  async function sendChat(message) {
    const log = $("#chat-log");
    const empty = log.querySelector(".chat-empty");
    if (empty) empty.remove();
    const user = document.createElement("div");
    user.className = "bubble user";
    user.textContent = message;
    log.appendChild(user);
    const pending = document.createElement("div");
    pending.className = "bubble bot";
    pending.textContent = "…";
    log.appendChild(pending);
    log.scrollTop = log.scrollHeight;
    try {
      const res = await api("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      pending.textContent = res.response || "(empty)";
      refreshMissions();
      refreshCouncils();
      refreshStats();
    } catch (e) {
      pending.textContent = "Error: " + e.message;
    }
    log.scrollTop = log.scrollHeight;
  }

  // ── missions ────────────────────────────────────────────────────────────
  function bindMissions() {
    $("#btn-launch").addEventListener("click", launchMission);
    $("#btn-launch-council").addEventListener("click", () => {
      const g = $("#mission-goal").value.trim();
      if (!g) return $("#mission-goal").focus();
      $("#council-goal").value = g;
      showView("council");
      launchCouncil();
    });
    $("#btn-cancel").addEventListener("click", cancelActive);
    $("#btn-refresh-missions").addEventListener("click", refreshMissions);
    $("#btn-copy-result").addEventListener("click", () =>
      copyText($("#result-body").textContent, $("#btn-copy-result"))
    );
  }

  async function launchMission() {
    const goal = $("#mission-goal").value.trim();
    if (!goal) return $("#mission-goal").focus();
    const maxSteps = Number($("#max-steps").value) || 12;
    state.mode = "mission";
    state.activeId = null;
    resetTrace("trace");
    clearTraceEmpty("trace");
    $("#result-panel").hidden = true;
    $("#btn-launch").disabled = true;
    $("#btn-cancel").disabled = false;
    $("#home-status").textContent = "Launching solo mission…";
    appendStep("trace", "system", "…", "Launching solo mission…", goal.slice(0, 100));
    try {
      const mission = await api("/api/missions", {
        method: "POST",
        body: JSON.stringify({ goal, max_steps: maxSteps, wait: false }),
      });
      state.activeId = mission.id;
      $("#active-mission-label").textContent = `${mission.id} · running`;
      appendStep("trace", "system", "0", `Queued ${mission.id}`);
      followMission(mission.id);
      refreshMissions();
    } catch (e) {
      appendStep("trace", "obs err", "!", e.message);
      $("#btn-launch").disabled = false;
      $("#btn-cancel").disabled = true;
    }
  }

  function followMission(mid) {
    try {
      const es = new EventSource(`/api/missions/${mid}/stream`);
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "snapshot" && data.mission) {
            const m = data.mission;
            if (["completed", "failed", "cancelled"].includes(m.status)) {
              if (m.result) showResult(m.result);
              if (m.error) showResult(m.error);
              $("#btn-launch").disabled = false;
              $("#btn-cancel").disabled = true;
              $("#active-mission-label").textContent = `${mid} · ${m.status}`;
              es.close();
              refreshMissions();
              refreshStats();
            }
          } else if (data.type !== "ping") {
            handleEvent(data);
            if (
              ["mission_completed", "mission_failed", "mission_cancelled"].includes(
                data.type
              )
            )
              es.close();
          }
        } catch (_) {}
      };
    } catch (_) {}
  }

  async function loadMission(mid) {
    try {
      const m = await api(`/api/missions/${mid}`);
      state.activeId = mid;
      state.mode = "mission";
      $("#active-mission-label").textContent = `${mid} · ${m.status}`;
      resetTrace("trace");
      clearTraceEmpty("trace");
      (m.steps || []).forEach((s) => {
        if (s.thought)
          appendStep("trace", "thought", s.index, s.thought, `→ ${s.action}`);
        if (s.action === "finish")
          appendStep("trace", "done", s.index, s.observation || "done");
        else {
          appendStep(
            "trace",
            "tool",
            s.index,
            `🔧 ${s.action}`,
            JSON.stringify(s.args || {})
          );
          appendStep(
            "trace",
            s.status === "success" ? "obs" : "obs err",
            s.index,
            s.observation || ""
          );
        }
      });
      if (m.result) showResult(m.result);
      if (m.error) showResult(m.error);
      renderMissionList($("#mission-list"), state.missions, loadMission);
    } catch (e) {
      console.warn(e);
    }
  }

  // ── council ─────────────────────────────────────────────────────────────
  function bindCouncil() {
    $("#btn-council").addEventListener("click", launchCouncil);
    $("#btn-council-cancel").addEventListener("click", cancelActive);
    $("#btn-refresh-council").addEventListener("click", refreshCouncils);
    $("#btn-copy-council").addEventListener("click", () =>
      copyText($("#council-result-body").textContent, $("#btn-copy-council"))
    );
  }

  async function launchCouncil() {
    const goal = $("#council-goal").value.trim();
    if (!goal) return $("#council-goal").focus();
    state.mode = "council";
    state.activeId = null;
    resetTrace("council-trace");
    clearTraceEmpty("council-trace");
    $("#council-result-panel").hidden = true;
    $("#tally-bar").hidden = true;
    $("#btn-council").disabled = true;
    $("#btn-home-council").disabled = true;
    $("#btn-council-cancel").disabled = false;
    $("#home-status").textContent = "Convening council…";
    appendStep("council-trace", "system", "…", "Convening Agent Council…", goal.slice(0, 100));
    try {
      const session = await api("/api/council", {
        method: "POST",
        body: JSON.stringify({
          goal,
          auto_execute: true,
          wait: false,
          use_chamber: $("#use-chamber").checked,
        }),
      });
      state.activeId = session.id;
      $("#council-active-label").textContent = `${session.id} · deliberating`;
      appendStep(
        "council-trace",
        "system",
        "0",
        `Council ${session.id}`,
        (session.seats || []).slice(0, 12).join(", ")
      );
      pollCouncil(session.id);
      refreshCouncils();
    } catch (e) {
      appendStep("council-trace", "obs err", "!", e.message);
      $("#btn-council").disabled = false;
      $("#btn-home-council").disabled = false;
      $("#btn-council-cancel").disabled = true;
    }
  }

  function pollCouncil(cid) {
    let n = 0;
    const tick = async () => {
      n += 1;
      try {
        const s = await api(`/api/council/${cid}`);
        if (["completed", "failed", "cancelled"].includes(s.status)) {
          $("#council-active-label").textContent = `${cid} · ${s.status}`;
          if (s.tally) {
            const bar = $("#tally-bar");
            bar.hidden = false;
            bar.innerHTML = Object.entries(s.tally)
              .map(
                ([k, v]) =>
                  `<span class="chip ${esc(k)}">${esc(k)}: ${esc(
                    typeof v === "number" ? v.toFixed(1) : v
                  )}</span>`
              )
              .join("");
          }
          showCouncilResult(formatCouncil(s));
          // hydrate sparse trace
          if ($("#council-trace").children.length < 4 && (s.opinions || []).length) {
            resetTrace("council-trace");
            clearTraceEmpty("council-trace");
            (s.opinions || []).forEach((o, i) => {
              appendStep(
                "council-trace",
                "thought",
                i + 1,
                `${o.seat_name} · ${o.round}: ${o.summary}`,
                o.stance
              );
            });
          }
          $("#btn-council").disabled = false;
          $("#btn-home-council").disabled = false;
          $("#btn-council-cancel").disabled = true;
          refreshCouncils();
          refreshStats();
          return;
        }
      } catch (_) {}
      if (n < 180) setTimeout(tick, 600);
    };
    setTimeout(tick, 500);
  }

  function formatCouncil(s) {
    const d = s.directive || {};
    const ex = s.execution || {};
    const lines = [
      `# ⚖ Vortex Agent Council`,
      `**Goal:** ${s.goal || ""}`,
      `**Decision:** ${(d.decision || s.status || "").toUpperCase()}`,
      `**Tally:** ${JSON.stringify(s.tally || {})}`,
      "",
      "## Members",
      ...(s.members || []).map(
        (m) => `- ${m.name || m.id} — ${m.project || ""}`
      ),
      "",
      "## Consensus",
      d.summary || s.consensus || "—",
      "",
      "## Plan",
      ...(d.actions || []).map((a, i) => `${i + 1}. ${a}`),
    ];
    if ((d.risks || []).length)
      lines.push("", "## Risks", ...d.risks.map((r) => `- ⚠ ${r}`));
    if ((s.dissent || []).length)
      lines.push("", "## Dissent", ...s.dissent.map((x) => `- ${x}`));
    lines.push(
      "",
      "## Execution",
      `mode=${ex.mode || "—"} workers=${ex.worker_count ?? "—"} status=${ex.status || "—"}`,
      ex.final_path ? `final: ${ex.final_path}` : "",
      "",
      ex.result || ex.summary || ex.error || ""
    );
    return lines.filter(Boolean).join("\n");
  }

  async function loadCouncil(cid) {
    try {
      const s = await api(`/api/council/${cid}`);
      state.activeId = cid;
      state.mode = "council";
      $("#council-active-label").textContent = `${cid} · ${s.status}`;
      resetTrace("council-trace");
      clearTraceEmpty("council-trace");
      (s.opinions || []).forEach((o, i) => {
        appendStep(
          "council-trace",
          "thought",
          i + 1,
          `${o.seat_name} · ${o.round}: ${o.summary}`,
          [o.stance, o.vote].filter(Boolean).join(" ")
        );
      });
      if (s.tally) {
        const bar = $("#tally-bar");
        bar.hidden = false;
        bar.innerHTML = Object.entries(s.tally)
          .map(
            ([k, v]) =>
              `<span class="chip ${esc(k)}">${esc(k)}: ${esc(
                typeof v === "number" ? v.toFixed(1) : v
              )}</span>`
          )
          .join("");
      }
      showCouncilResult(formatCouncil(s));
      renderMissionList($("#council-list"), state.councils, loadCouncil);
    } catch (e) {
      console.warn(e);
    }
  }

  async function cancelActive() {
    if (!state.activeId) return;
    try {
      if (state.mode === "council")
        await api(`/api/council/${state.activeId}/cancel`, { method: "POST" });
      else
        await api(`/api/missions/${state.activeId}/cancel`, { method: "POST" });
      if (state.ws && state.ws.readyState === 1)
        state.ws.send(
          JSON.stringify({ type: "cancel", mission_id: state.activeId })
        );
    } catch (e) {
      appendStep(
        state.mode === "council" ? "council-trace" : "trace",
        "obs err",
        "!",
        e.message
      );
    }
  }

  async function copyText(t, btn) {
    try {
      await navigator.clipboard.writeText(t || "");
      const old = btn.textContent;
      btn.textContent = "Copied";
      setTimeout(() => (btn.textContent = old), 1200);
    } catch (_) {}
  }

  boot();
})();
