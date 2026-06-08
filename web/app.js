"use strict";

// Python files to mount into the Pyodide virtual filesystem.
const PY_FILES = [
  "poker/__init__.py", "poker/cards.py", "poker/evaluator.py", "poker/equity.py",
  "poker/ranges.py", "poker/range_model.py", "poker/profiling.py", "poker/engine.py",
  "poker/table.py", "poker/simulator.py", "poker/tournament.py", "poker/history.py",
  "poker/coach.py",
  "poker/render.py", "poker/bots.py", "poker/arena.py",
  "poker/fast_equity.py", "web_api.py",
];

const SUIT = { s: "♠", h: "♥", d: "♦", c: "♣" };
const RED = new Set(["h", "d"]);

let pyodide = null;
let game = null;     // python WebGame proxy
let state = null;

async function boot() {
  const lt = document.getElementById("loadtext");
  pyodide = await loadPyodide();
  if (lt) lt.innerHTML = "Carico il motore veloce…<br/><small>(numpy)</small>";
  // numpy enables the vectorised equity path -> snappy bots in the browser.
  let fast = false;
  try { await pyodide.loadPackage("numpy"); fast = true; } catch (e) { fast = false; }

  pyodide.FS.mkdir("/app");
  pyodide.FS.mkdir("/app/poker");
  for (const f of PY_FILES) {
    const txt = await (await fetch("py/" + f)).text();
    pyodide.FS.writeFile("/app/" + f, txt);
  }
  pyodide.runPython("import sys; sys.path.insert(0, '/app')");
  // turn on the fast equity path and keep iteration counts web-friendly
  pyodide.runPython(`
import poker.engine as _e
_e.USE_FAST_EQUITY = ${fast ? "True" : "False"}
_e.EQUITY_ITERS = 400
`);
  document.getElementById("loader").hidden = true;
  document.getElementById("app").hidden = false;
  bindUI();
  openSetup();
}

function newGame(villains, stack) {
  const py = pyodide.runPython(`
import web_api
_g = web_api.WebGame(villains=${JSON.stringify(villains.split(","))}, stack=${stack})
_g
`);
  game = py;
  nextHand();
}

function call(method, ...args) {
  const argStr = args.map(a => JSON.stringify(a)).join(", ");
  const res = pyodide.runPython(`import json; json.dumps(_g.${method}(${argStr}))`);
  return JSON.parse(res);
}

function thinking(on) {
  const m = document.getElementById("message");
  if (on) { m.textContent = "🤖 i bot pensano…"; }
}

// Run a (blocking) python step after letting the browser repaint first, so the
// UI never looks frozen during equity computation.
function defer(fn) {
  thinking(true);
  document.getElementById("controls").hidden = true;
  requestAnimationFrame(() => requestAnimationFrame(() => {
    try { fn(); } catch (e) { document.getElementById("message").textContent = "Errore: " + e; }
  }));
}

function nextHand() { defer(() => { state = call("start_hand"); render(); }); }
function submit(action, amount) { defer(() => { state = call("submit", action, amount); render(); }); }

// ---- rendering --------------------------------------------------------
function cardEl(cs, small) {
  const d = document.createElement("div");
  d.className = "pcard" + (small ? " sm" : "");
  if (!cs) { d.classList.add("back"); d.textContent = ""; return d; }
  const suit = cs[1].toLowerCase();
  d.classList.add(RED.has(suit) ? "red" : "black");
  d.textContent = cs[0] + (SUIT[suit] || "?");
  return d;
}

function render() {
  const winners = state.winners || {};
  // opponents
  const opp = document.getElementById("opponents");
  opp.innerHTML = "";
  for (const p of state.players) {
    if (p.is_hero) continue;
    const s = document.createElement("div");
    s.className = "seat" + (p.folded ? " folded" : "") + (winners[p.name] ? " win" : "");
    s.innerHTML = `<div class="nm">${p.name}</div><div class="pos">${p.position||""}</div>
      <div class="stk">${p.stack} BB</div>
      <div class="act">${winners[p.name] ? "▲ +" + winners[p.name] : ""}</div>`;
    const cw = document.createElement("div");
    cw.style.cssText = "display:flex;gap:4px;justify-content:center;margin-top:4px";
    const holes = p.hole && p.hole.length ? p.hole : [null, null];
    holes.forEach(c => cw.appendChild(cardEl(c, true)));
    s.appendChild(cw);
    opp.appendChild(s);
  }
  // board
  const board = document.getElementById("board");
  board.innerHTML = "";
  (state.board || []).forEach(c => board.appendChild(cardEl(c, false)));
  document.getElementById("pot").textContent = "Piatto: " + (state.pot || 0) + " BB";

  // hero
  const hero = state.players.find(p => p.is_hero);
  const hc = document.getElementById("hero-cards");
  hc.innerHTML = "";
  const hole = state.hero_hole || hero.hole || [];
  (hole.length ? hole : [null, null]).forEach(c => hc.appendChild(cardEl(c, false)));
  document.getElementById("hero-info").textContent =
    `${hero.name} · ${hero.position || ""} · ${hero.stack} BB`;

  const coach = document.getElementById("coach");
  const controls = document.getElementById("controls");
  const nexth = document.getElementById("nexthand");
  const msg = document.getElementById("message");

  if (state.need_action) {
    msg.textContent = "";
    coach.hidden = false; controls.hidden = false; nexth.hidden = true;
    const c = state.coach, lg = state.legal;
    const insights = c.insights || {};
    const outs = insights.outs || {};
    const eqb = insights.equity_breakdown || {};
    document.getElementById("coach-line").textContent = "💡 Coach: " + c.label;
    const odds = lg.to_call > 0 ? Math.round(100 * lg.to_call / (lg.pot + lg.to_call)) : 0;
    document.getElementById("coach-odds").textContent =
      `equity ${Math.round(c.equity*100)}% · da pagare ${lg.to_call} · pot-odds ${odds}%`;
    document.getElementById("coach-reason").textContent = c.reason;
    document.getElementById("coach-made").textContent =
      `mano attuale: ${insights.made_hand || "n/d"}${(insights.draws || []).length ? " · draw: " + insights.draws.join(", ") : ""}`;
    document.getElementById("coach-outs").textContent =
      `outs per migliorare: ${outs.count || 0} · prossima carta ${Math.round((outs.next_card_pct || 0)*100)}% · entro river ${Math.round((outs.by_river_pct || 0)*100)}%`;
    const breakdownBits = [
      `win ${Math.round((eqb.win_pct || 0) * 100)}%`,
      `tie ${Math.round((eqb.tie_pct || 0) * 100)}%`,
      `lose ${Math.round((eqb.lose_pct || 0) * 100)}%`,
    ];
    if (insights.heads_up_equity) {
      breakdownBits.push(`HU ${Math.round(insights.heads_up_equity * 100)}%`);
    }
    if (insights.vs_betting_range_equity) {
      breakdownBits.push(`vs range forte ${Math.round(insights.vs_betting_range_equity * 100)}%`);
    }
    document.getElementById("coach-breakdown").textContent = breakdownBits.join(" · ");

    const callBtn = document.getElementById("btn-call");
    callBtn.textContent = lg.can_check ? "Check" : ("Call " + lg.to_call);
    const r = document.getElementById("raise-amt");
    r.min = lg.min_raise_to; r.max = lg.max_raise_to;
    let def = (c.action === "raise" && c.amount) ? c.amount : lg.min_raise_to;
    r.value = Math.min(Math.max(def, lg.min_raise_to), lg.max_raise_to);
    document.getElementById("raise-val").textContent = r.value;
    document.getElementById("btn-raise").textContent = "Rilancia a";
    // hide raise if not possible
    document.querySelector(".raisebox").style.display =
      (lg.max_raise_to > lg.min_raise_to) ? "flex" : "none";
  } else {
    coach.hidden = true; controls.hidden = true; nexth.hidden = false;
    const wtxt = Object.entries(winners).map(([n, a]) => `${n} +${a}`).join(", ");
    msg.textContent = wtxt ? ("Vince: " + wtxt) : "";
  }
}

// ---- UI bindings ------------------------------------------------------
function openSetup() { document.getElementById("setup").hidden = false; }

function bindUI() {
  document.getElementById("btn-fold").onclick = () => submit("fold", 0);
  document.getElementById("btn-call").onclick = () => {
    const lg = state.legal;
    submit(lg.can_check ? "check" : "call", lg.to_call);
  };
  document.getElementById("btn-raise").onclick = () =>
    submit("raise", parseFloat(document.getElementById("raise-amt").value));
  document.getElementById("btn-coach").onclick = () =>
    submit(state.coach.action, state.coach.amount);
  document.getElementById("raise-amt").oninput = e =>
    document.getElementById("raise-val").textContent = e.target.value;
  document.getElementById("btn-next").onclick = () => nextHand();
  document.getElementById("newgame").onclick = openSetup;
  document.getElementById("cfg-start").onclick = () => {
    document.getElementById("setup").hidden = true;
    newGame(document.getElementById("cfg-villains").value,
            parseFloat(document.getElementById("cfg-stack").value) || 100);
  };
}

// PWA: register the service worker so the app is installable + works offline.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () =>
    navigator.serviceWorker.register("sw.js").catch(() => {}));
}

boot();
