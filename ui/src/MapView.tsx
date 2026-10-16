// The live map: pages are nodes (size = importance), actions are folded into edges.
// Green = fully tested, amber = untried work, red border = bugs, red edge = broken in this release,
// dashed = only seen in the previous release. Explorers are shown on the page they are working on.
import cytoscape, { Core } from "cytoscape";
import { useEffect, useRef } from "react";
import type { Agent, Edge, State } from "./api";

type Props = { states: State[]; edges: Edge[]; agents: Agent[]; onPick: (key: string) => void };

function stateOfWork(work: string | null): string | null {
  if (!work) return null;
  const target = work.slice(work.indexOf(":") + 1);
  return target.includes("#") ? target.split("#")[0] : null;
}

export function MapView({ states, edges, agents, onPick }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);

  useEffect(() => {
    if (!box.current) return;
    cy.current = cytoscape({
      container: box.current,
      wheelSensitivity: 0.2,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)", "font-size": 8, color: "#e8e8f0", "text-valign": "bottom", "text-margin-y": 3,
            "text-background-color": "#11131c", "text-background-opacity": 0.75, "text-background-padding": "1px",
            "text-wrap": "wrap", "text-max-width": "120px", width: "data(size)", height: "data(size)",
            "background-color": "data(color)", "border-width": "data(border)", "border-color": "#ff5c5c",
          },
        },
        { selector: "node[?entry]", style: { shape: "diamond" } },
        {
          selector: "edge",
          style: {
            width: 1.2, "line-color": "#5b6078", "target-arrow-color": "#5b6078", "target-arrow-shape": "triangle",
            "curve-style": "bezier", "arrow-scale": 0.7, opacity: 0.8,
          },
        },
        { selector: "edge[!ok]", style: { "line-color": "#ff5c5c", "target-arrow-color": "#ff5c5c", width: 2 } },
        { selector: "edge[?stale]", style: { "line-style": "dashed", opacity: 0.35 } },
        { selector: "node:selected", style: { "border-width": 3, "border-color": "#7aa2ff" } },
      ],
    });
    cy.current.on("tap", "node", (e) => onPick(e.target.id()));
    return () => cy.current?.destroy();
  }, []);

  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    const maxImp = Math.max(1, ...states.map((s) => s.importance ?? 0));
    const here = new Map<string, string[]>();
    for (const a of agents) {
      const k = stateOfWork(a.state === "working" ? a.work : null);
      if (k) here.set(k, [...(here.get(k) ?? []), a.name.replace("explorer-", "e")]);
    }
    const added: string[] = [];
    c.batch(() => {
      for (const s of states) {
        const who = here.get(s.key);
        const data = {
          id: s.key, entry: s.entry,
          label: `${s.name}${s.bugs ? `  ⚠${s.bugs}` : ""}${who ? `\n[${who.join(",")}]` : ""}`,
          size: 14 + 26 * Math.sqrt((s.importance ?? 0) / maxImp),
          color: s.open > 0 ? "#f0a73a" : "#3fbf7f", border: s.bugs ? 3 : 0,
        };
        const n = c.getElementById(s.key);
        if (n.empty()) {
          const parent = edges.find((e) => e.target === s.key && !c.getElementById(e.source).empty());
          const p = parent ? c.getElementById(parent.source).position() : { x: 0, y: 0 };
          c.add({ group: "nodes", data, position: { x: p.x + 80 * (Math.random() - 0.3), y: p.y + 60 + 40 * Math.random() } });
          added.push(s.key);
        } else n.data(data);
      }
      const ids = new Set<string>();
      for (const e of edges) {
        if (e.source === e.target && e.ok) continue; // actions that stay on the page add only clutter
        const id = `${e.action_key}|${e.target}|${e.release}`;
        ids.add(id);
        const data = { id, source: e.source, target: e.target, ok: e.ok, stale: !!e.stale };
        if (c.getElementById(e.source).empty() || c.getElementById(e.target).empty()) continue;
        const el = c.getElementById(id);
        if (el.empty()) c.add({ group: "edges", data });
        else el.data(data);
      }
      c.edges().filter((e) => !ids.has(e.id())).remove();
      const keys = new Set(states.map((s) => s.key));
      c.nodes().filter((n) => !keys.has(n.id())).remove();
    });
    if (added.length) {
      c.layout({
        name: "cose", animate: added.length < 6, randomize: false, nodeRepulsion: () => 400000,
        idealEdgeLength: () => 110, nodeOverlap: 20, gravity: 0.3, numIter: 1500, componentSpacing: 80,
      } as any).run();
      if (added.length === c.nodes().length) c.fit(undefined, 30);
    }
  }, [states, edges, agents]);

  return <div ref={box} className="map" />;
}
