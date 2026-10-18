import { useCallback, useEffect, useRef, useState } from "react";
import { ago, api, type Agent, type Bug, type Edge, type Overview, type State } from "./api";
import { Guide } from "./Guide";
import { MapView } from "./MapView";
import { Activity, BugDrawer, Bugs, Cypher, Diff, Growth, LlmChart, StateDrawer, Swarm } from "./panels";

type Data = {
  overview?: Overview; states: State[]; edges: Edge[]; bugs: Bug[]; agents: Agent[]; jobs: any[];
  sessions: any[]; growth: { kind: string; at: number }[]; diff: any; calls: any[]; facts: any[]; timeline: any[];
};
const EMPTY: Data = {
  states: [], edges: [], bugs: [], agents: [], jobs: [], sessions: [], growth: [], diff: null, calls: [], facts: [],
  timeline: [],
};

function seenGuide(): boolean {
  try { return localStorage.getItem("clew.guide") === "seen"; } catch { return false; }
}

export function App() {
  const [d, setD] = useState<Data>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const [pickState, setPickState] = useState<string | null>(null);
  const [pickBug, setPickBug] = useState<string | null>(null);
  const [guide, setGuide] = useState(!seenGuide());
  const [toast, setToast] = useState<{ text: string; bad?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ explorers: 4, minutes: 10, mode: "shared", start_from: "fresh" });
  const timer = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [overview, map, bugs, agents, jobs, sessions, growth, diff, calls, facts, timeline] = await Promise.all([
        api.overview(), api.map(), api.bugs(), api.agents(), api.jobs(), api.sessions(), api.growth(), api.diff(),
        api.toolcalls(), api.facts(), api.timeline(),
      ]);
      setD({ overview, states: map.states, edges: map.edges, bugs, agents, jobs, sessions, growth, diff, calls, facts, timeline });
      setErr(null);
    } catch (e) {
      setErr(String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const poll = window.setInterval(load, 5000);
    const es = new EventSource("/api/stream");
    const kick = () => {
      if (timer.current) return;
      timer.current = window.setTimeout(() => { timer.current = null; load(); }, 700);
    };
    for (const ev of ["state.created", "transition", "claim", "bug.updated", "job.updated", "release.changed", "toolcall", "session", "mission", "action.healed"]) {
      es.addEventListener(ev, kick);
    }
    return () => { window.clearInterval(poll); es.close(); };
  }, [load]);

  const closeGuide = () => {
    try { localStorage.setItem("clew.guide", "seen"); } catch { /* private mode: show it again next time */ }
    setGuide(false);
  };
  const notify = (text: string, bad = false) => {
    setToast({ text, bad });
    window.setTimeout(() => setToast(null), 5000);
  };
  const act = async (label: string, fn: () => Promise<any>, ok: (r: any) => string) => {
    setBusy(true);
    try { const r = await fn(); notify(ok(r)); await load(); } catch (e) { notify(`${label} failed: ${String(e).replace("Error: ", "")}`, true); }
    setBusy(false);
  };
  const mission = async (key: string) => {
    const text = prompt("What should the testers focus on, on this page?", "Test invalid coupon codes");
    if (text) act("Mission", () => api.mission(key, text), (r) => `Mission ${r.mission} added: ${r.actions.length} new test cases`);
  };

  const o = d.overview;
  const session = o?.session;
  const left = session ? Math.max(0, session.started_at + session.minutes * 60_000 - Date.now()) : 0;
  const dup = session ? d.sessions.find((s) => s.id === session.id)?.duplicates ?? 0 : d.sessions[0]?.duplicates ?? null;
  const live = d.agents.filter((a) => a.role === "explorer" && a.state !== "stopped" && Date.now() - a.last_seen < 30_000).length;
  const filed = d.bugs.filter((b) => ["filed", "fixed"].includes(b.status)).length;
  const cov = o?.coverage;
  const mapEmpty = d.states.length === 0;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <h1>Clew</h1>
          <span className="tagline">AI testers that share one map in FalkorDB</span>
        </div>
        <span className="pill rel" title="The release of the store currently being tested">Store release <b>{o?.release ?? "–"}</b></span>
        <span className={`pill ${session ? "running" : ""}`}>
          {session ? <>● Session {session.id} running · {Math.floor(left / 60000)}:{String(Math.floor((left % 60000) / 1000)).padStart(2, "0")} left</> : "No session running"}
        </span>
        <span className="pill muted" title="Which model reads new pages and writes reports ('off' = rule-based, no model)">LLM: {o?.llm}</span>
        <div className="header-links">
          {o?.store_url && <a className="btn" href={o.store_url} target="_blank" rel="noreferrer">Open the store ↗</a>}
          <button onClick={() => setGuide(true)}>Guide</button>
        </div>
      </header>

      <section className="controls-bar">
        <div className="control-group">
          <div className="group-title"><span className="num">1</span> Run a test session</div>
          <div className="group-body">
            <label>Testers<input type="number" min={1} max={8} value={form.explorers} disabled={!!session}
              onChange={(e) => setForm({ ...form, explorers: +e.target.value })} /></label>
            <label>Minutes<input type="number" min={1} max={60} value={form.minutes} disabled={!!session}
              onChange={(e) => setForm({ ...form, minutes: +e.target.value })} /></label>
            <label title="Fresh: reset the store and start an empty map. Continue: keep the map (memory). v1 snapshot: start from the saved v1 map.">Map
              <select value={form.start_from} disabled={!!session} onChange={(e) => setForm({ ...form, start_from: e.target.value })}>
                <option value="fresh">Fresh map</option><option value="continue">Continue map</option><option value="v1_snapshot">v1 snapshot</option>
              </select></label>
            <label title="Shared: one map for all testers (the normal mode). Isolated: each tester has its own private map (the comparison experiment).">Memory
              <select value={form.mode} disabled={!!session} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
                <option value="shared">Shared</option><option value="isolated">Isolated</option>
              </select></label>
            {!session ? (
              <button className="primary" disabled={busy} onClick={() => act("Start", () => api.startSession(form), (r) => `Session ${r.session} started with ${r.explorers} testers for ${r.minutes} minutes`)}>▶ Start</button>
            ) : (
              <button className="danger" disabled={busy} onClick={() => act("Stop", () => api.stopSession(session.id), () => `Session ${session.id} stopped`)}>■ Stop</button>
            )}
          </div>
        </div>
        <div className="control-group">
          <div className="group-title"><span className="num">2</span> Try a scenario <small>(while a session runs)</small></div>
          <div className="group-body">
            <button disabled={busy || !session} title="Force-kill one tester mid-task. Its unfinished work is picked up by another tester when its lease expires."
              onClick={() => act("Kill", api.kill, (r) => r.killed ? `Killed one tester (${r.killed}); it rejoins in a few seconds as a new tester` : r.error)}>✖ Kill a tester</button>
            {o?.release === "v1" ? (
              <button disabled={busy} title="Ship release v2 of the store. Every known route is replayed and compared with v1."
                onClick={() => act("Deploy", () => api.release("v2"), () => "Store switched to v2: the release watcher is replaying every known route")}>⇪ Deploy v2</button>
            ) : (
              <button disabled={busy} title="Switch the store back to release v1"
                onClick={() => act("Roll back", () => api.release("v1"), () => "Store switched back to v1")}>↶ Roll back to v1</button>
            )}
            {!o?.hosted && <button disabled={busy} title="Restart every service, the database included. The map survives."
              onClick={() => act("Restart", api.restartAll, () => "Restarting every service; the map is kept")}>⟳ Restart services</button>}
            <button disabled={busy || !!session} title="Reset the store to v1 and erase the map"
              onClick={() => confirm("Reset the store to v1 and erase the map?") && act("Reset", api.reset, () => "Store reset and map erased")}>⌫ Reset everything</button>
          </div>
        </div>
        <div className="status-line">
          {cov ? <>
            <b>{live}</b> testers working · <b>{cov.states}</b> kinds of page · <b>{cov.done}</b>/{cov.actions} actions tested ·{" "}
            <b>{filed}</b> bugs filed · duplicate work <b className={dup ? "bad" : "good"}>{dup ?? 0}</b>
          </> : "Loading…"}
        </div>
      </section>

      {err && <div className="error">Can't reach the API: {err}</div>}
      <main className="grid">
        <aside className="col">
          <Swarm agents={d.agents.filter((a) => a.role === "explorer")} coverage={cov} jobs={d.jobs} duplicates={dup} />
          <Activity rows={d.timeline} />
          <section>
            <h2>What the testers learned</h2>
            <p className="hint">Facts stored in the graph and reused later: preconditions, how inputs were received, renamed buttons.</p>
            <ul className="small">{d.facts.length ? d.facts.map((f, i) => <li key={i}><b>{f.kind}</b> {f.text}</li>) : <li className="muted">Nothing yet.</li>}</ul>
          </section>
          <section>
            <h2>Background agents</h2>
            <ul className="agents">{d.agents.filter((a) => a.role !== "explorer").map((a) => <li key={a.name}>● {a.name} <small>{a.role} · {a.state} · {ago(a.last_seen)}</small></li>)}</ul>
          </section>
        </aside>
        <section className="center">
          <div className="center-head">
            <h2>Live map of the store</h2>
            <p className="hint">Each circle is a kind of page, each arrow an action. Size = how many routes pass through it (tested first). Click a page for details.</p>
          </div>
          <div className="map-wrap">
            <MapView states={d.states} edges={d.edges} agents={d.agents} onPick={setPickState} />
            {mapEmpty && (
              <div className="map-empty">
                <h3>The map is empty</h3>
                <p>Press <b>▶ Start</b> above. The testers open the store, and every new kind of page appears here as they find it.</p>
              </div>
            )}
          </div>
          <div className="legend">
            ◆ entry page · <span className="good">●</span> fully tested · <span className="amber">●</span> work left ·
            <span className="bad"> ◯</span> bug found · <span className="bad">→</span> broken in this release · dashed = previous release only · [e1] = tester here now
          </div>
          <div className="charts"><Growth points={d.growth} /><LlmChart sessions={d.sessions} /></div>
        </section>
        <aside className="col">
          <Bugs bugs={d.bugs} onPick={setPickBug} />
          <Diff diff={d.diff} onPickBug={setPickBug} />
          <Cypher calls={d.calls} />
        </aside>
      </main>
      {pickState && <StateDrawer stateKey={pickState} onClose={() => setPickState(null)} onMission={mission} />}
      {pickBug && <BugDrawer sig={pickBug} onClose={() => setPickBug(null)} />}
      {guide && <Guide onClose={closeGuide} storeUrl={o?.store_url} />}
      {toast && <div className={`toast ${toast.bad ? "bad-bg" : ""}`}>{toast.text}</div>}
    </div>
  );
}
