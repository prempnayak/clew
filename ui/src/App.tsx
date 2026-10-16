import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Agent, type Bug, type Edge, type Overview, type State } from "./api";
import { MapView } from "./MapView";
import { BugDrawer, Bugs, Cypher, Diff, Growth, LlmChart, StateDrawer, Swarm } from "./panels";

type Data = {
  overview?: Overview; states: State[]; edges: Edge[]; bugs: Bug[]; agents: Agent[]; jobs: any[];
  sessions: any[]; growth: { kind: string; at: number }[]; diff: any; calls: any[]; facts: any[];
};
const EMPTY: Data = { states: [], edges: [], bugs: [], agents: [], jobs: [], sessions: [], growth: [], diff: null, calls: [], facts: [] };

export function App() {
  const [d, setD] = useState<Data>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const [pickState, setPickState] = useState<string | null>(null);
  const [pickBug, setPickBug] = useState<string | null>(null);
  const [form, setForm] = useState({ explorers: 4, minutes: 10, mode: "shared", start_from: "fresh" });
  const timer = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [overview, map, bugs, agents, jobs, sessions, growth, diff, calls, facts] = await Promise.all([
        api.overview(), api.map(), api.bugs(), api.agents(), api.jobs(), api.sessions(), api.growth(), api.diff(),
        api.toolcalls(), api.facts(),
      ]);
      setD({ overview, states: map.states, edges: map.edges, bugs, agents, jobs, sessions, growth, diff, calls, facts });
      setErr(null);
    } catch (e) {
      setErr(String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const poll = window.setInterval(load, 5000);
    const es = new EventSource("/api/stream");
    es.onmessage = es.onerror = null;
    const kick = () => {
      if (timer.current) return;
      timer.current = window.setTimeout(() => { timer.current = null; load(); }, 700);
    };
    for (const ev of ["state.created", "transition", "claim", "bug.updated", "job.updated", "release.changed", "toolcall", "session", "mission", "action.healed"]) {
      es.addEventListener(ev, kick);
    }
    return () => { window.clearInterval(poll); es.close(); };
  }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    try { await fn(); await load(); } catch (e) { alert(String(e)); }
  };
  const mission = async (key: string) => {
    const text = prompt("Mission for this page", "Test invalid coupon codes");
    if (text) act(() => api.mission(key, text));
  };

  const o = d.overview;
  const session = o?.session;
  const left = session ? Math.max(0, session.started_at + session.minutes * 60_000 - Date.now()) : 0;
  const dup = session ? d.sessions.find((s) => s.id === session.id)?.duplicates ?? 0 : d.sessions[0]?.duplicates ?? null;

  return (
    <div className="app">
      <header className="top">
        <h1>Clew <small>war room</small></h1>
        <span className="pill">graph {o?.graph}</span>
        <span className="pill rel">release {o?.release ?? "–"}</span>
        <span className="pill">{session ? `session ${session.id} · ${session.mode} · ${session.explorers} explorers · ${Math.floor(left / 60000)}:${String(Math.floor((left % 60000) / 1000)).padStart(2, "0")} left` : "no session running"}</span>
        <span className="pill muted">LLM {o?.llm} · filing {o?.filing}</span>
        <div className="controls">
          {!session ? (
            <>
              <input type="number" min={1} max={8} value={form.explorers} onChange={(e) => setForm({ ...form, explorers: +e.target.value })} title="explorers" />
              <input type="number" min={1} max={60} value={form.minutes} onChange={(e) => setForm({ ...form, minutes: +e.target.value })} title="minutes" />
              <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}><option>shared</option><option>isolated</option></select>
              <select value={form.start_from} onChange={(e) => setForm({ ...form, start_from: e.target.value })}><option value="fresh">fresh map</option><option value="continue">continue map</option><option value="v1_snapshot">v1 snapshot</option></select>
              <button className="primary" onClick={() => act(() => api.startSession(form))}>Start</button>
            </>
          ) : (
            <button onClick={() => act(() => api.stopSession(session.id))}>Stop</button>
          )}
          <button onClick={() => act(api.kill)} title="S2: SIGKILL one explorer">Kill explorer</button>
          {!o?.hosted && <button onClick={() => act(api.restartAll)} title="S3">Restart all</button>}
          {o?.release === "v1" ? <button onClick={() => act(() => api.release("v2"))} title="S4">Deploy v2</button> : <button onClick={() => act(() => api.release("v1"))}>Roll back</button>}
          <button onClick={() => confirm("Reset the store and start a fresh map?") && act(api.reset)}>Reset map</button>
        </div>
      </header>
      {err && <div className="error">API: {err}</div>}
      <main className="grid">
        <aside className="col">
          <Swarm agents={d.agents.filter((a) => a.role === "explorer")} coverage={o?.coverage} jobs={d.jobs} duplicates={dup} />
          <section>
            <h2>Other agents</h2>
            <ul className="agents">{d.agents.filter((a) => a.role !== "explorer").map((a) => <li key={a.name}>● {a.name} <small>{a.role} · {a.state}</small></li>)}</ul>
          </section>
          <section>
            <h2>Memory: facts</h2>
            <ul className="small">{d.facts.map((f, i) => <li key={i}><b>{f.kind}</b> {f.text}</li>)}</ul>
          </section>
        </aside>
        <section className="center">
          <MapView states={d.states} edges={d.edges} agents={d.agents} onPick={setPickState} />
          <div className="legend">◆ entry · <span className="good">●</span> fully tested · <span style={{ color: "#f0a73a" }}>●</span> untried work · red ring = bug · <span className="bad">—</span> broken in this release · dashed = previous release only · size = betweenness</div>
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
    </div>
  );
}
