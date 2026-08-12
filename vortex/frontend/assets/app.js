/* Vortex Agent — Mission Control frontend */
(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  const state = {
    activeMissionId: null,
    ws: null,
    wsRetries: 0,
    bots: [],
    tools: [],
    missions: [],
  };

  // ── boot ──────────────────────────────────────────────────────────────
  async function boot() {
    await Promise.all([refreshMeta(), refreshMissions(), refreshStats()]);
    connectWs();
    bindUi();
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
      ...opts,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText);
    }
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return res.text();
  }

  // ── data loads ────────────────────────────────────────────────────────
  async function refreshMeta() {
    try {
      const [health, meta] = await Promise.all([
        api("/health"),
        api("/api/meta"),
      ]);
      setPill("pill-health", "ok", `online · v${health.version || "0.3"}`);
      setPill("pill-provider", "dim", `brain: ${meta.provider || "offline"}`);
      setPill("pill-bots", "dim", `bots: ${meta.bots?.length ?? health.bots}`);
      state.bots = meta.bots || [];
      state.tools = meta.tools || [];
      renderBots();
      renderTools();
    } catch (e) {
      setPill("pill-health", "bad", "offline");
      console.warn(e);
    }
  }

  async function refreshStats() {
    try {
      const s = await api("/api/stats");
      const grid = $("#stat-grid");
      const items = [
        ["Messages", s.messages ?? 0],
        ["Tool calls", s.tool_calls ?? 0],
        ["Missions", s.missions ?? 0],
        ["Tools", s.tools ?? 0],
      ];
      grid.innerHTML = items
        .map(
          ([k, v]) =>
            `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`
        )
        .join("");
    } catch (_) {}
  }

  async function refreshMissions() {
    try {
      state.missions = await api("/api/missions");
      renderMissions();
    } catch (_) {}
  }

  function setPill(id, cls, text) {
    const el = $("#" + id);
    if (!el) return;
    el.className = "pill " + (cls === "dim" ? "dim" : cls);
    const dot = cls === "dim" ? "" : "<i></i>";
    el.innerHTML = `${dot}${text}`;
  }

  // ── renderers ─────────────────────────────────────────────────────────
  const BOT_ICON = {
    orchestrator: "🧠",
    research: "🔍",
    coding: "🏗️",
    security: "🔒",
    scout: "🛰️",
    general: "🤖",
  };

  function renderBots() {
    const ul = $("#bot-list");
    ul.innerHTML = state.bots
      .map(
        (b) => `
      <li data-bot="${esc(b.name)}">
        <div class="bot-avatar">${BOT_ICON[b.role] || "🤖"}</div>
        <div class="bot-meta">
          <div class="name">${esc(b.name)}</div>
          <div class="role">${esc(b.role)} · ${b.messages || 0} msgs</div>
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

  function renderMissions() {
    const ul = $("#mission-list");
    if (!state.missions.length) {
      ul.innerHTML = `<li class="muted" style="border:none;background:transparent">No missions yet</li>`;
      return;
    }
    ul.innerHTML = state.missions
      .slice(0, 20)
      .map((m) => {
        const active = m.id === state.activeMissionId ? "active" : "";
        return `
        <li class="${active}" data-mid="${esc(m.id)}">
          <div class="mission-meta" style="width:100%">
            <div style="display:flex;justify-content:space-between;gap:8px;align-items:center">
              <div class="name">${esc(m.id)}</div>
              <span class="badge ${esc(m.status)}">${esc(m.status)}</span>
            </div>
            <div class="sub">${esc((m.goal || "").slice(0, 70))}</div>
            <div class="sub">${m.step_count || 0} steps</div>
          </div>
        </li>`;
      })
      .join("");

    ul.querySelectorAll("li[data-mid]").forEach((li) => {
      li.addEventListener("click", () => loadMission(li.dataset.mid));
    });
  }

  // ── websocket ─────────────────────────────────────────────────────────
  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${location.host}/ws`;
    try {
      state.ws = new WebSocket(url);
    } catch (e) {
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
    if (!ev || !ev.type) return;
    if (ev.type === "hello" || ev.type === "pong" || ev.type === "ping") return;

    // only render events for active mission (or if none selected, adopt it)
    const mid = ev.mission_id;
    if (mid && !state.activeMissionId) {
      state.activeMissionId = mid;
      $("#active-mission-label").textContent = mid;
      $("#btn-cancel").disabled = false;
    }
    if (mid && state.activeMissionId && mid !== state.activeMissionId) {
      // still refresh mission list on terminal events
      if (String(ev.type).startsWith("mission_")) refreshMissions();
      return;
    }

    switch (ev.type) {
      case "mission_queued":
      case "mission_started":
        clearTraceEmpty();
        appendStep("system", "0", `Mission ${ev.type.replace("mission_", "")}: ${ev.goal || mid}`);
        $("#btn-cancel").disabled = false;
        break;
      case "thinking":
        // soft indicator — skip noisy duplicates
        break;
      case "thought":
        clearTraceEmpty();
        appendStep(
          "thought",
          ev.step,
          ev.thought || "(planning)",
          ev.action ? `next: ${ev.action}` : ""
        );
        break;
      case "tool_call":
        clearTraceEmpty();
        appendStep(
          "tool",
          ev.step,
          `🔧 ${ev.tool}`,
          ev.args ? JSON.stringify(ev.args, null, 0) : ""
        );
        break;
      case "observation":
        clearTraceEmpty();
        appendStep(
          ev.status === "success" ? "obs" : "obs err",
          ev.step,
          ev.observation || "",
          ""
        );
        break;
      case "mission_completed":
        appendStep("done", "✓", "Mission completed", `${ev.steps || "?"} steps`);
        showResult(ev.result || "");
        $("#btn-cancel").disabled = true;
        $("#btn-launch").disabled = false;
        refreshMissions();
        refreshStats();
        break;
      case "mission_failed":
        appendStep("obs err", "✗", `Failed: ${ev.error || "unknown"}`);
        $("#btn-cancel").disabled = true;
        $("#btn-launch").disabled = false;
        refreshMissions();
        break;
      case "mission_cancelled":
        appendStep("system", "–", "Mission cancelled");
        $("#btn-cancel").disabled = true;
        $("#btn-launch").disabled = false;
        refreshMissions();
        break;
      default:
        break;
    }
  }

  function clearTraceEmpty() {
    const empty = $("#trace .trace-empty");
    if (empty) empty.remove();
  }

  function appendStep(kind, idx, body, args) {
    const trace = $("#trace");
    const el = document.createElement("div");
    el.className = "step";
    const kindClass = kind.startsWith("obs")
      ? kind
      : kind;
    el.innerHTML = `
      <div class="idx">#${esc(String(idx))}</div>
      <div>
        <span class="kind ${esc(kindClass.split(" ")[0])}${
      kind.includes("err") ? " err" : ""
    }">${esc(kind.replace(" err", ""))}</span>
        <div class="body">${esc(body)}${
      args ? `<div class="args">${esc(args)}</div>` : ""
    }</div>
      </div>`;
    // fix err class on kind span
    if (kind.includes("err")) {
      el.querySelector(".kind").classList.add("err");
    }
    if (kind === "done") {
      el.querySelector(".kind").className = "kind done";
    }
    trace.appendChild(el);
    trace.scrollTop = trace.scrollHeight;
  }

  function resetTrace() {
    $("#trace").innerHTML = "";
    $("#result-panel").hidden = true;
    $("#result-body").textContent = "";
  }

  function showResult(text) {
    $("#result-panel").hidden = false;
    $("#result-body").textContent = text || "(empty)";
  }

  // ── actions ───────────────────────────────────────────────────────────
  function bindUi() {
    $("#btn-launch").addEventListener("click", launchMission);
    $("#btn-chat").addEventListener("click", () => {
      const g = $("#goal-input").value.trim();
      if (g) sendChat(g);
      else $("#chat-input").focus();
    });
    $("#btn-cancel").addEventListener("click", cancelMission);
    $("#btn-refresh-bots").addEventListener("click", refreshMeta);
    $("#btn-refresh-missions").addEventListener("click", refreshMissions);
    $("#btn-copy-result").addEventListener("click", async () => {
      const t = $("#result-body").textContent;
      try {
        await navigator.clipboard.writeText(t);
        $("#btn-copy-result").textContent = "Copied";
        setTimeout(() => ($("#btn-copy-result").textContent = "Copy"), 1200);
      } catch (_) {}
    });

    $$("#goal-chips button").forEach((btn) => {
      btn.addEventListener("click", () => {
        $("#goal-input").value = btn.dataset.goal || btn.textContent;
        $("#goal-input").focus();
      });
    });

    $("#chat-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const v = $("#chat-input").value.trim();
      if (!v) return;
      $("#chat-input").value = "";
      sendChat(v);
    });

    $("#goal-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        launchMission();
      }
    });
  }

  async function launchMission() {
    const goal = $("#goal-input").value.trim();
    if (!goal) {
      $("#goal-input").focus();
      return;
    }
    const maxSteps = Number($("#max-steps").value) || 12;
    resetTrace();
    clearTraceEmpty();
    appendStep("system", "…", "Launching mission…", goal.slice(0, 120));
    $("#btn-launch").disabled = true;
    $("#btn-cancel").disabled = false;
    $("#result-panel").hidden = true;

    try {
      const mission = await api("/api/missions", {
        method: "POST",
        body: JSON.stringify({ goal, max_steps: maxSteps, wait: false }),
      });
      state.activeMissionId = mission.id;
      $("#active-mission-label").textContent = `${mission.id} · running`;
      appendStep("system", "0", `Queued ${mission.id}`, `provider: ${mission.provider}`);
      // also follow via SSE as a reliable fallback
      followSse(mission.id);
      refreshMissions();
    } catch (e) {
      appendStep("obs err", "!", `Failed to launch: ${e.message}`);
      $("#btn-launch").disabled = false;
      $("#btn-cancel").disabled = true;
    }
  }

  function followSse(mid) {
    // SSE complements WS — useful behind proxies that buffer WS oddly
    try {
      const es = new EventSource(`/api/missions/${mid}/stream`);
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.type === "snapshot" && data.mission) {
            // hydrate any steps we missed
            const m = data.mission;
            if (m.status === "completed" && m.result) {
              // don't double-render if WS already did
            }
            if (["completed", "failed", "cancelled"].includes(m.status)) {
              if (m.result) showResult(m.result);
              if (m.error) showResult(m.error);
              $("#btn-launch").disabled = false;
              $("#btn-cancel").disabled = true;
              $("#active-mission-label").textContent = `${mid} · ${m.status}`;
              // paint steps if trace is nearly empty
              const steps = m.steps || [];
              if ($("#trace").children.length < 3 && steps.length) {
                resetTrace();
                steps.forEach((s) => {
                  if (s.thought)
                    appendStep("thought", s.index, s.thought, `action: ${s.action}`);
                  appendStep(
                    s.status === "success" ? "obs" : "obs err",
                    s.index,
                    `${s.action}: ${s.observation || ""}`
                  );
                });
                if (m.result) showResult(m.result);
              }
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
            ) {
              es.close();
            }
          }
        } catch (_) {}
      };
      es.onerror = () => {
        // let it retry natively a bit; close after terminal is handled elsewhere
      };
    } catch (_) {}
  }

  async function cancelMission() {
    if (!state.activeMissionId) return;
    try {
      await api(`/api/missions/${state.activeMissionId}/cancel`, { method: "POST" });
      if (state.ws && state.ws.readyState === 1) {
        state.ws.send(
          JSON.stringify({ type: "cancel", mission_id: state.activeMissionId })
        );
      }
    } catch (e) {
      appendStep("obs err", "!", `Cancel failed: ${e.message}`);
    }
  }

  async function loadMission(mid) {
    try {
      const m = await api(`/api/missions/${mid}`);
      state.activeMissionId = mid;
      $("#active-mission-label").textContent = `${mid} · ${m.status}`;
      resetTrace();
      clearTraceEmpty();
      (m.steps || []).forEach((s) => {
        if (s.thought)
          appendStep("thought", s.index, s.thought, `→ ${s.action}`);
        if (s.action === "finish") {
          appendStep("done", s.index, s.observation || "done");
        } else {
          appendStep(
            s.status === "success" ? "tool" : "obs err",
            s.index,
            `🔧 ${s.action}`,
            JSON.stringify(s.args || {})
          );
          appendStep(
            s.status === "success" ? "obs" : "obs err",
            s.index,
            s.observation || ""
          );
        }
      });
      if (m.result) showResult(m.result);
      if (m.error) showResult(m.error);
      $("#btn-cancel").disabled = m.status !== "running";
      $("#btn-launch").disabled = m.status === "running";
      renderMissions();
    } catch (e) {
      console.warn(e);
    }
  }

  async function sendChat(message) {
    const log = $("#chat-log");
    const user = document.createElement("div");
    user.className = "bubble user";
    user.textContent = message;
    log.appendChild(user);
    log.scrollTop = log.scrollHeight;

    const pending = document.createElement("div");
    pending.className = "bubble bot";
    pending.textContent = "…";
    log.appendChild(pending);

    try {
      const res = await api("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      pending.textContent = res.response || "(empty)";
      refreshStats();
      refreshMissions();
    } catch (e) {
      pending.textContent = "Error: " + e.message;
    }
    log.scrollTop = log.scrollHeight;
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  boot();
})();
