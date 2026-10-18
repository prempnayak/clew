import { useEffect, useState } from "react";
import { ago, api, type Agent, type Bug, type Coverage } from "./api";

// -- swarm ------------------------------------------------------------------------------------------------------
export function Swarm({ agents, coverage, jobs, duplicates }: { agents: Agent[]; coverage?: Coverage; jobs: any[]; duplicates: number | null }) {
  const live = agents.filter((a) => Date.now() - a.last_seen < 30_000);
  const queued = jobs.filter((j) => j.status === "queued" || j.status === "claimed");
  return (
    <section>
      <h2>AI testers</h2>
      <p className="hint">Each tester claims one task at a time from the graph, walks the shortest known route to it and records what happened. Grey = stopped.</p>
      {agents.filter((a) => Date.now() - a.last_seen < 120_000).length === 0 && (
        <p className="muted">No testers running. Start a session.</p>
      )}
      <ul className="agents">
        {agents.filter((a) => Date.now() - a.last_seen < 120_000).map((a) => {
          const alive = Date.now() - a.last_seen < 30_000;
          const stopped = a.state === "stopped";
          return (
            <li key={a.name} className={alive && !stopped ? "" : "dead"} title={a.work ?? ""}>
              <span className="dot">{alive && !stopped ? "●" : "○"}</span> {a.name}
              <small> {a.state === "working" ? shortWork(a.work) : a.state} · {ago(a.last_seen)}</small>
            </li>
          );
        })}
      </ul>
      {agents.some((a) => Date.now() - a.last_seen >= 120_000) && (
        <p className="muted small-note">+ {agents.filter((a) => Date.now() - a.last_seen >= 120_000).length} testers from earlier sessions (stopped)</p>
      )}
      {coverage && (
        <dl className="stats">
          <dt title="Distinct kinds of page in the map">Kinds of page</dt><dd>{coverage.states}</dd>
          <dt title="Actions tested / actions known">Actions tested</dt><dd>{coverage.done}/{coverage.actions}</dd>
          <dt title="Tasks currently held by a tester (each claim expires after 2 minutes)">Tasks in progress</dt><dd>{coverage.claimed}</dd>
          <dt title="Confirm, replay and verify-fix jobs waiting">Jobs waiting</dt><dd>{queued.length}</dd>
          <dt title="Actions run by more than one tester in this session (query Q32). Should be 0.">Duplicate work</dt><dd className={duplicates ? "bad" : "good"}>{duplicates ?? "–"}</dd>
          <dt>Testers alive</dt><dd>{live.length}</dd>
        </dl>
      )}
    </section>
  );
}

function shortWork(w: string | null): string {
  if (!w) return "";
  const [kind, ...rest] = w.split(":");
  const target = rest.join(":");
  const label = target.includes("#") ? target.split("#")[1] : target;
  return `${kind} → ${label.slice(0, 40)}`;
}

// -- bugs -------------------------------------------------------------------------------------------------------
const PIPELINE = ["suspect", "new", "confirming", "confirmed", "filed", "fixed", "not_reproduced"];

export function Bugs({ bugs, onPick }: { bugs: Bug[]; onPick: (sig: string) => void }) {
  const shown = bugs.filter((b) => b.status !== "suspect");
  const suspects = bugs.length - shown.length;
  return (
    <section>
      <h2>Bugs found</h2>
      <p className="hint">A problem becomes a bug report only after another tester reproduces it from scratch in a fresh browser. Click a bug for the steps and screenshot.</p>
      <div className="pipeline">
        {PIPELINE.map((s) => (
          <span key={s} className={`chip ${s}`}>{s.replace("_", " ")} {bugs.filter((b) => b.status === s).length}</span>
        ))}
      </div>
      <ul className="bugs">
        {shown.map((b) => (
          <li key={b.sig} onClick={() => onPick(b.sig)}>
            <span className={`sev ${b.severity}`}>{b.severity}</span>
            {b.issue ? <b>#{b.issue}</b> : null} {b.title}
            <small className={`status ${b.status}`}> {b.status}</small>
            <div className="pages">{b.kind} · {b.pages.join(", ")}</div>
          </li>
        ))}
      </ul>
      {shown.length === 0 && <p className="muted">No bugs yet.</p>}
      {suspects > 0 && <p className="muted">{suspects} suspect(s) not reported: console noise or glitches seen while replaying, which never count as bugs.</p>}
    </section>
  );
}

// -- release diff ------------------------------------------------------------------------------------------------
export function Diff({ diff, onPickBug }: { diff: any; onPickBug: (sig: string) => void }) {
  if (!diff?.previous) return <section><h2>Release diff</h2><p className="hint">After you press <b>Deploy v2</b>, every route the testers know is replayed on the new release and the differences appear here.</p></section>;
  const c = diff.changes ?? { renames: [], fixed: [], still: [], new_pages: [] };
  const fixed = (c.fixed ?? []).filter((f: any) => f.sig);
  const still = (c.still ?? []).filter((f: any) => f.sig);
  const pages = (c.new_pages ?? []).filter((p: any) => p.key);
  return (
    <section>
      <h2>Release diff {diff.previous} → {diff.current}</h2>
      <p className="hint">Every known route was replayed on {diff.current}. Regressions are filed as bugs; renamed buttons are recognised; fixed bugs are closed.</p>
      <p className="diffline">
        <span className="bad">✗ {diff.regressions.length} broken step(s) → {new Set(diff.regressions.map((r: any) => r.action.split("|")[0] + "#" + r.action.split("#")[1])).size} regression issue(s)</span> · ↻ {(c.renames ?? []).length} renamed ·
        <span className="good"> ✓ {fixed.length} fixed</span> · ＋ {pages.length} new page(s) · {still.length} still present
        {diff.variants?.length ? ` · ~ ${diff.variants.length} changed layout (not filed)` : ""}
        {diff.replays_pending?.pending ? ` · ${diff.replays_pending.pending} replays pending` : ""}
      </p>
      <ul className="small">
        {diff.regressions.map((r: any) => (
          <li key={r.action}>✗ <b>{r.label}</b> on {r.page} ({r.change}): was {r.was_target}, now {r.now_target}{r.error ? ` (${r.error.slice(0, 70)})` : ""}</li>
        ))}
        {(diff.variants ?? []).map((r: any) => (
          <li key={r.action} className="muted">~ {r.label} on {r.page}: same page, different layout ({r.now_target})</li>
        ))}
        {(c.renames ?? []).map((t: string) => <li key={t}>↻ {t}</li>)}
        {fixed.map((f: any) => <li key={f.sig} onClick={() => onPickBug(f.sig)}>✓ #{f.issue} {f.title}</li>)}
        {pages.map((p: any) => <li key={p.key}>＋ {p.name}</li>)}
      </ul>
    </section>
  );
}

// -- charts (plain SVG) -----------------------------------------------------------------------------------------
export function Growth({ points }: { points: { kind: string; at: number }[] }) {
  if (points.length < 2) return <div className="chart muted">Map growth appears as pages are found.</div>;
  const t0 = points[0].at, t1 = points[points.length - 1].at || t0 + 1;
  const W = 300, H = 90;
  const line = (kind: string) => {
    const pts = points.filter((p) => p.kind === kind);
    const max = Math.max(1, pts.length);
    return pts.map((p, i) => `${((p.at - t0) / Math.max(1, t1 - t0)) * W},${H - ((i + 1) / max) * H}`).join(" ");
  };
  const states = points.filter((p) => p.kind === "state").length;
  const actions = points.filter((p) => p.kind === "action").length;
  return (
    <div className="chart">
      <h3>Map growth</h3>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
        <polyline points={line("action")} fill="none" stroke="#f0a73a" strokeWidth="1.5" />
        <polyline points={line("state")} fill="none" stroke="#3fbf7f" strokeWidth="1.5" />
      </svg>
      <small><span className="good">■ {states} pages</span> <span style={{ color: "#f0a73a" }}>■ {actions} actions</span> over {Math.round((t1 - t0) / 1000)} s</small>
    </div>
  );
}

export function LlmChart({ sessions }: { sessions: any[] }) {
  const rows = [...sessions].reverse().map((s) => {
    const actions = (s.llm ?? []).reduce((n: number, r: any) => n + r.actions, 0);
    const calls = s.stats?.llm_calls ?? 0;
    return { id: s.id, mode: s.mode, ratio: actions ? calls / actions : 0, calls, actions, dups: s.duplicates };
  });
  if (!rows.length) return <div className="chart muted">Page-reader calls per new action appear per session.</div>;
  const max = Math.max(0.01, ...rows.map((r) => r.ratio));
  return (
    <div className="chart">
      <h3>Page-reader calls per newly tested action</h3>
      {rows.map((r) => (
        <div key={r.id} className="bar">
          <span>{r.id} {r.mode}</span>
          <div style={{ width: `${(r.ratio / max) * 100}%` }} />
          <small>{r.calls}/{r.actions} · dup {r.dups}</small>
        </div>
      ))}
    </div>
  );
}

// -- Show Cypher -------------------------------------------------------------------------------------------------
export function Cypher({ calls }: { calls: any[] }) {
  const [open, setOpen] = useState<any | null>(null);
  const showQuery = async (qid: string) => {
    const q = await api.query(qid);
    setOpen({ tool: `${q.id} ${q.name}`, summary: q.purpose, trace: [{ qid: q.id, cypher: q.cypher, params: q.params, rows: [] }] });
  };
  return (
    <section>
      <h2>Graph queries (under the hood)</h2>
      <p className="hint">Every decision is a Cypher query on FalkorDB. ★ = the key ones; below, each tool call the Reporter agent made and the queries it ran.</p>
      <ul className="small calls">
        <li className="fixed" onClick={() => showQuery("Q06")}>★ Q06 claim_action: how explorers split work</li>
        <li className="fixed" onClick={() => showQuery("Q09")}>★ Q09 importance: betweenness centrality</li>
        <li className="fixed" onClick={() => showQuery("Q11")}>★ Q11 repro_steps: shortest path to a bug</li>
        <li className="fixed" onClick={() => showQuery("Q19")}>★ Q19 regressions: per-release edge diff</li>
        {calls.map((c) => (
          <li key={c.id} onClick={async () => setOpen(await api.toolcall(c.id))}>
            <span className={c.ok ? "good" : "bad"}>{c.ok ? "✓" : "✗"}</span> {c.agent} · <b>{c.tool}</b> · {c.query_ids.join(", ")} <small>{ago(c.at)}</small>
          </li>
        ))}
      </ul>
      {open && (
        <Drawer title={open.tool} onClose={() => setOpen(null)}>
          {open.summary && <p>{open.summary}</p>}
          {open.trace?.map((t: any, i: number) => (
            <div key={i}>
              <h4>{t.qid}{t.ms != null ? ` · ${t.ms} ms` : ""}</h4>
              <pre className="cypher">{t.cypher}</pre>
              <details><summary>parameters</summary><pre>{typeof t.params === "string" ? t.params : JSON.stringify(t.params, null, 1)}</pre></details>
              {t.rows?.length > 0 && <details><summary>first rows</summary><pre>{JSON.stringify(t.rows, null, 1)}</pre></details>}
            </div>
          ))}
        </Drawer>
      )}
    </section>
  );
}

// -- drawers -----------------------------------------------------------------------------------------------------
export function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="drawer-bg" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <header><h3>{title}</h3><button onClick={onClose}>✕</button></header>
        {children}
      </aside>
    </div>
  );
}

export function StateDrawer({ stateKey, onClose, onMission }: { stateKey: string; onClose: () => void; onMission: (key: string) => void }) {
  const [s, setS] = useState<any>(null);
  useEffect(() => { api.state(stateKey).then(setS); }, [stateKey]);
  if (!s) return null;
  return (
    <Drawer title={s.name} onClose={onClose}>
      <p className="mono">{s.key}</p>
      <p>Importance {Math.round(s.importance ?? 0)} · visits {s.visits} · first seen by {s.first_seen_by} · <a href={`/api/states/${encodeURIComponent(s.key)}`} target="_blank">JSON</a></p>
      <button onClick={() => onMission(s.key)}>Add mission on this page…</button>
      <h4>Actions</h4>
      <ul className="small">
        {s.actions.map((a: any) => (
          <li key={a.key} title={a.key}>
            <span className={`status ${a.status}`}>{a.status}</span> {a.label}
            {a.input_case ? <small> ({a.origin})</small> : null}
            {a.aliases?.length ? <small> · was “{a.aliases.join("”, “")}”</small> : null}
            {a.skip_reason ? <small> · {a.skip_reason}</small> : null}
          </li>
        ))}
      </ul>
      {s.facts.length > 0 && (<><h4>Facts</h4><ul className="small">{s.facts.map((f: string) => <li key={f}>{f}</li>)}</ul></>)}
    </Drawer>
  );
}

export function BugDrawer({ sig, onClose }: { sig: string; onClose: () => void }) {
  const [b, setB] = useState<any>(null);
  useEffect(() => { api.bug(sig).then(setB); }, [sig]);
  if (!b) return null;
  const ev = b.evidence ?? {};
  return (
    <Drawer title={`${b.issue ? `#${b.issue} ` : ""}${b.issue_title ?? b.title}`} onClose={onClose}>
      <p><span className={`sev ${b.severity}`}>{b.severity}</span> <span className={`status ${b.status}`}>{b.status}</span> · {b.kind} · found in {b.release_found} · seen in {b.seen_in.join(", ")}{b.fixed_in.length ? ` · fixed in ${b.fixed_in.join(", ")}` : ""}</p>
      <p className="mono">{b.sig}</p>
      {b.issue_url && <p>Issue: {b.issue_url.startsWith("dry-run") ? <span>{b.issue_url} (dry run)</span> : <a href={b.issue_url} target="_blank">{b.issue_url}</a>}</p>}
      <h4>Repro steps (shortest path, Q11)</h4>
      <pre>{b.repro?.text ?? "no known route"}</pre>
      <h4>Evidence</h4>
      <p>{ev.message}</p>
      <p className="muted">Found by {ev.agent} (run {ev.run}, step {ev.step}){b.same_as.length ? ` · merged into ${b.same_as.join(", ")}` : ""}</p>
      {ev.screenshot && <img className="shot" src={`/api/screenshots/${ev.screenshot}`} alt="screenshot at the time of the bug" />}
      {b.issue_body && (<><h4>Issue body</h4><pre className="issue">{b.issue_body}</pre></>)}
    </Drawer>
  );
}

// -- live activity -----------------------------------------------------------------------------------------------
const KIND: Record<string, string> = {
  explore: "explored", mission: "mission", variation: "tried another item", confirm: "re-checked a bug",
  replay: "replayed on new release", verify_fix: "checked a fix",
};

export function Activity({ rows }: { rows: any[] }) {
  return (
    <section>
      <h2>Live activity</h2>
      <p className="hint">The latest steps, newest first. Every one is read from and written to the graph.</p>
      <ul className="small activity">
        {rows.length === 0 && <li className="muted">Nothing yet.</li>}
        {rows.map((r, i) => (
          <li key={i}>
            <span className={r.ok ? "good" : "bad"}>{r.ok ? "✓" : "✗"}</span> <b>{r.agent.replace("explorer-", "tester ")}</b>{" "}
            {KIND[r.kind] ?? r.kind}: {r.label} <small>{ago(r.at)}</small>
          </li>
        ))}
      </ul>
    </section>
  );
}
