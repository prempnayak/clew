// Thin client for the Clew API. Every endpoint is backed by a named Cypher query (see /api/queries).

export type State = {
  key: string; name: string; route: string; auth: string; importance: number | null;
  entry: boolean; first_seen: number; actions: number; open: number; bugs: number;
};
export type Edge = {
  source: string; target: string; action: string; action_key: string; ok: boolean; cost: number;
  release: string; stale?: boolean;
};
export type Bug = {
  sig: string; title: string; kind: string; severity: string; status: string; issue: number | null;
  issue_url: string | null; first_seen: number; release_found: string; pages: string[];
};
export type Agent = { name: string; role: string; state: string; work: string | null; session: string | null; last_seen: number };
export type Coverage = { states: number; actions: number; done: number; untried: number; claimed: number; bugs: number };
export type Overview = {
  graph: string; release: string | null; previous: string | null; hosted: boolean; filing: string; llm: string;
  session: { id: string; mode: string; explorers: number; minutes: number; started_at: number } | null;
  coverage: Coverage;
};

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

async function post<T>(path: string, body: unknown = {}): Promise<T> {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error ?? data.detail ?? `${path}: ${r.status}`);
  return data;
}

const enc = encodeURIComponent;

export const api = {
  overview: () => get<Overview>("/api/overview"),
  map: () => get<{ states: State[]; edges: Edge[] }>("/api/map"),
  state: (key: string) => get<any>(`/api/states/${enc(key)}`),
  bugs: () => get<Bug[]>("/api/bugs"),
  bug: (sig: string) => get<any>(`/api/bugs/${enc(sig)}`),
  agents: () => get<Agent[]>("/api/agents"),
  jobs: () => get<any[]>("/api/jobs?limit=200"),
  sessions: () => get<any[]>("/api/sessions"),
  facts: () => get<any[]>("/api/facts?limit=12"),
  growth: () => get<{ kind: string; at: number }[]>("/api/growth"),
  diff: () => get<any>("/api/diff"),
  toolcalls: () => get<any[]>("/api/toolcalls?limit=25"),
  toolcall: (id: string) => get<any>(`/api/toolcalls/${enc(id)}`),
  query: (qid: string) => get<any>(`/api/queries/${enc(qid)}`),
  startSession: (b: { explorers: number; minutes: number; mode: string; start_from: string }) => post("/api/sessions", b),
  stopSession: (id: string) => post(`/api/sessions/${enc(id)}/stop`),
  kill: () => post("/api/explorers/kill"),
  restartAll: () => post("/api/restart-all"),
  release: (release: string) => post("/api/release", { release }),
  reset: () => post("/api/reset"),
  mission: (state: string, text: string) => post("/api/missions", { state, text }),
};

export function ago(ms: number | null | undefined): string {
  if (!ms) return "";
  const s = Math.max(0, Math.round((Date.now() - ms) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}
