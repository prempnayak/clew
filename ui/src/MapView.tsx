// The live map: pages are nodes (size = importance), actions between two pages are folded into one arrow
// (thicker = more actions; red = at least one is broken in this release; dashed = only seen in the previous release).
// Layout: fCoSE, which takes label sizes into account so pages and labels don't overlap. New pages start next to
// the page that led to them and the layout settles incrementally, so existing pages stay roughly where they were.
import cytoscape, { Core } from "cytoscape";
import fcose from "cytoscape-fcose";
import { useEffect, useRef } from "react";
import type { Agent, Edge, State } from "./api";

cytoscape.use(fcose);

type Props = { states: State[]; edges: Edge[]; agents: Agent[]; onPick: (key: string) => void };

const LAYOUT = {
  name: "fcose",
  quality: "default",
  nodeDimensionsIncludeLabels: true, // spacing accounts for labels, not just circles
  nodeSeparation: 90,
  idealEdgeLength: 130,
  nodeRepulsion: 9000,
  edgeElasticity: 0.3,
  gravity: 0.2,
  numIter: 2500,
  packComponents: true,
  padding: 30,
};

function stateOfWork(work: string | null): string | null {
  if (!work) return null;
  const target = work.slice(work.indexOf(":") + 1);
  return target.includes("#") ? target.split("#")[0] : null;
}

type Arrow = { id: string; source: string; target: string; count: number; ok: boolean; stale: boolean; labels: string[] };

/** One arrow per page pair (and release freshness), instead of one per action. */
function foldEdges(edges: Edge[]): Arrow[] {
  const out = new Map<string, Arrow>();
  for (const e of edges) {
    if (e.source === e.target && e.ok) continue; // staying on the same page adds only clutter
    const stale = !!e.stale;
    const id = `${e.source}->${e.target}${stale ? "|old" : ""}`;
    const a = out.get(id) ?? { id, source: e.source, target: e.target, count: 0, ok: true, stale, labels: [] };
    a.count += 1;
    a.ok = a.ok && e.ok;
    if (a.labels.length < 6) a.labels.push(e.action);
    out.set(id, a);
  }
  return [...out.values()];
}

/** Fit everything in view, but never zoom in so far that a small map looks huge. */
function fitView(c: Core, animate = true) {
  const opts = { padding: 30 };
  const eles = c.elements();
  if (!eles.length) return;
  if (animate) {
    c.animate({ fit: { eles, ...opts }, duration: 300, complete: () => capZoom(c) } as any);
  } else {
    c.fit(eles, opts.padding);
    capZoom(c);
  }
}

function capZoom(c: Core) {
  if (c.zoom() > 1.25) {
    c.zoom(1.25);
    c.center();
  }
}

/** Re-fit only when something has drifted out of view, so the picture doesn't jump for nothing. */
function keepInView(c: Core) {
  const bb = c.elements().boundingBox();
  const ext = c.extent();
  if (bb.x1 < ext.x1 || bb.x2 > ext.x2 || bb.y1 < ext.y1 || bb.y2 > ext.y2) fitView(c);
}

export function MapView({ states, edges, agents, onPick }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const layoutTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!box.current) return;
    cy.current = cytoscape({
      container: box.current,
      wheelSensitivity: 0.25,
      minZoom: 0.2,
      maxZoom: 3,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)", "font-size": 9, color: "#e8e8f0", "text-valign": "bottom", "text-margin-y": 4,
            "text-wrap": "wrap", "text-max-width": "110px", width: "data(size)", height: "data(size)",
            "text-background-color": "#11131c", "text-background-opacity": 0.8, "text-background-padding": "2px",
            "background-color": "data(color)", "border-width": "data(border)", "border-color": "#ff5c5c",
          },
        },
        { selector: "node[?entry]", style: { shape: "diamond" } },
        { selector: "node[?busy]", style: { "overlay-color": "#7aa2ff", "overlay-opacity": 0.18, "overlay-padding": 6 } },
        {
          selector: "edge",
          style: {
            width: "data(width)", "line-color": "#5b6078", "target-arrow-color": "#5b6078", "target-arrow-shape": "triangle",
            "curve-style": "bezier", "arrow-scale": 0.8, opacity: 0.55,
          },
        },
        { selector: "edge[!ok]", style: { "line-color": "#ff5c5c", "target-arrow-color": "#ff5c5c", opacity: 0.95 } },
        { selector: "edge[?stale]", style: { "line-style": "dashed", opacity: 0.3 } },
        { selector: "node:selected", style: { "border-width": 3, "border-color": "#7aa2ff" } },
        // hovering a page highlights its arrows and fades the rest
        { selector: ".faded", style: { opacity: 0.12 } },
        { selector: "edge.hl", style: { opacity: 1, "line-color": "#7aa2ff", "target-arrow-color": "#7aa2ff" } },
      ],
    });
    const c = cy.current;
    c.on("tap", "node", (e) => onPick(e.target.id()));
    c.on("mouseover", "node", (e) => {
      const n = e.target;
      c.elements().addClass("faded");
      n.closedNeighborhood().removeClass("faded");
      n.connectedEdges().addClass("hl");
    });
    c.on("mouseout", "node", () => c.elements().removeClass("faded hl"));
    return () => c.destroy();
  }, []);

  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    const firstLoad = c.nodes().length === 0;
    const maxImp = Math.max(1, ...states.map((s) => s.importance ?? 0));
    const here = new Map<string, string[]>();
    for (const a of agents) {
      const k = stateOfWork(a.state === "working" ? a.work : null);
      if (k) here.set(k, [...(here.get(k) ?? []), a.name.replace("explorer-", "e")]);
    }
    const arrows = foldEdges(edges);
    let added = 0;
    c.batch(() => {
      const placedAround = new Map<string, number>();
      for (const s of states) {
        const who = here.get(s.key);
        const data = {
          id: s.key, entry: s.entry, busy: !!who,
          label: `${s.name}${s.bugs ? `  ⚠${s.bugs}` : ""}${who ? `\n[${who.join(",")}]` : ""}`,
          size: 16 + 28 * Math.sqrt((s.importance ?? 0) / maxImp),
          color: s.open > 0 ? "#f0a73a" : "#3fbf7f", border: s.bugs ? 3 : 0,
        };
        const n = c.getElementById(s.key);
        if (n.nonempty()) { n.data(data); continue; }
        // start next to the page that leads here (or the entry page), each new neighbour at its own angle
        const parentId = arrows.find((a) => a.target === s.key && c.getElementById(a.source).nonempty())?.source
          ?? c.nodes("[?entry]").first().id();
        const parent = parentId ? c.getElementById(parentId) : null;
        const base = parent && parent.nonempty() ? parent.position() : { x: 0, y: 0 };
        const k = (placedAround.get(parentId ?? "") ?? (parent && parent.nonempty() ? parent.degree(false) : 0)) + 1;
        placedAround.set(parentId ?? "", k);
        const angle = k * 2.399; // golden angle: neighbours never land on the same spot
        const r = 120 + 25 * Math.floor(k / 5);
        c.add({ group: "nodes", data, position: { x: base.x + r * Math.cos(angle), y: base.y + r * Math.sin(angle) } });
        added += 1;
      }
      const ids = new Set<string>();
      for (const a of arrows) {
        if (c.getElementById(a.source).empty() || c.getElementById(a.target).empty()) continue;
        ids.add(a.id);
        const data = { id: a.id, source: a.source, target: a.target, ok: a.ok, stale: a.stale,
                       width: Math.min(1 + a.count * 0.6, 5), title: a.labels.join(", ") };
        const el = c.getElementById(a.id);
        if (el.empty()) c.add({ group: "edges", data });
        else el.data(data);
      }
      c.edges().filter((e) => !ids.has(e.id())).remove();
      const keys = new Set(states.map((s) => s.key));
      c.nodes().filter((n) => !keys.has(n.id())).remove();
    });
    if (firstLoad && c.nodes().length) {
      c.layout({ ...LAYOUT, randomize: true, animate: false, fit: false } as any).run();
      fitView(c, false);
    } else if (added) {
      // settle new pages in place, at most once per 1.5 s, keeping everyone else close to where they were
      if (layoutTimer.current) window.clearTimeout(layoutTimer.current);
      layoutTimer.current = window.setTimeout(() => {
        layoutTimer.current = null;
        const l = c.layout({ ...LAYOUT, randomize: false, animate: true, animationDuration: 400, fit: false } as any);
        l.one("layoutstop", () => keepInView(c));
        l.run();
      }, 1500);
    }
  }, [states, edges, agents]);

  const fit = () => {
    const c = cy.current;
    if (!c) return;
    const l = c.layout({ ...LAYOUT, randomize: false, animate: true, animationDuration: 400, fit: false } as any);
    l.one("layoutstop", () => fitView(c));
    l.run();
  };

  return (
    <>
      <div ref={box} className="map" />
      <button className="map-fit" onClick={fit} title="Tidy the layout and fit the whole map in view">⤢ Fit</button>
    </>
  );
}
