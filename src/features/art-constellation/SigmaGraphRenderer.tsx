import { useEffect, useRef } from "react";
import Graph from "graphology";
import Sigma from "sigma";
import type { NodeLabelDrawingFunction } from "sigma/rendering";
import { DottedEdgeProgram } from "./DottedEdgeProgram";
import { localize, type ArtistRecord, type LayoutNode, type RelationshipRecord } from "./types";
import type { Locale } from "../../i18n/translations";

type SigmaGraphRendererProps = {
  artists: ArtistRecord[];
  relationships: RelationshipRecord[];
  layout: LayoutNode[];
  locale: Locale;
  focusArtistId: string | null;
  selectedRelationshipId: string | null;
  relatedArtistIds: Set<string>;
  onSelectArtist: (artistId: string) => void;
  onSelectRelationship: (relationshipId: string) => void;
  onReady: () => void;
  onUnavailable: (reason: "unavailable" | "context-lost") => void;
};

const EDGE_COLORS = {
  shared_subject: "216, 181, 109",
  shared_material: "127, 196, 189",
  shared_technique: "201, 167, 216",
} as const;

const drawContainedNodeLabel: NodeLabelDrawingFunction = (context, data, settings) => {
  if (!data.label) return;
  const color = settings.labelColor.attribute
    ? String(data[settings.labelColor.attribute] ?? settings.labelColor.color ?? "#000")
    : settings.labelColor.color ?? "#d7e2e2";
  context.fillStyle = color;
  context.font = `${settings.labelWeight} ${settings.labelSize}px ${settings.labelFont}`;
  const textWidth = context.measureText(data.label).width;
  const scale = Math.max(1, context.getTransform().a);
  const canvasWidth = context.canvas.width / scale;
  const rightX = data.x + data.size + 3;
  const leftX = data.x - data.size - 3 - textWidth;
  const x = rightX + textWidth <= canvasWidth - 8 || leftX < 8 ? rightX : leftX;
  context.fillText(data.label, x, data.y + settings.labelSize / 3);
};

function hasWebGl() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export default function SigmaGraphRenderer({
  artists,
  relationships,
  layout,
  locale,
  focusArtistId,
  selectedRelationshipId,
  relatedArtistIds,
  onSelectArtist,
  onSelectRelationship,
  onReady,
  onUnavailable,
}: SigmaGraphRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);
  const rendererRef = useRef<Sigma | null>(null);
  const artistsRef = useRef(artists);
  const relationshipStateRef = useRef({ relationships, focusArtistId, selectedRelationshipId, relatedArtistIds });
  const callbacksRef = useRef({ onSelectArtist, onSelectRelationship, onReady, onUnavailable });
  const artistKey = artists.map((artist) => artist.id).join("|");

  useEffect(() => {
    artistsRef.current = artists;
    relationshipStateRef.current = { relationships, focusArtistId, selectedRelationshipId, relatedArtistIds };
    callbacksRef.current = { onSelectArtist, onSelectRelationship, onReady, onUnavailable };
  }, [artists, focusArtistId, onReady, onSelectArtist, onSelectRelationship, onUnavailable, relatedArtistIds, relationships, selectedRelationshipId]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !hasWebGl()) {
      callbacksRef.current.onUnavailable("unavailable");
      return;
    }

    const positions = new Map(layout.map((node) => [node.artistId, node]));
    const graph = new Graph({ type: "undirected", multi: true, allowSelfLoops: false });
    const currentArtists = artistsRef.current;
    const currentState = relationshipStateRef.current;
    for (const artist of currentArtists) {
      const position = positions.get(artist.id);
      if (!position) {
        callbacksRef.current.onUnavailable("unavailable");
        return;
      }
      const isFocused = artist.id === currentState.focusArtistId;
      const isRelated = !currentState.focusArtistId || currentState.relatedArtistIds.has(artist.id);
      graph.addNode(artist.id, {
        x: position.x,
        y: position.y,
        size: 8,
        label: localize(artist.labels, locale),
        color: isFocused ? "#f0dca8" : isRelated ? "#7fc4bd" : "#49595d",
        highlighted: isFocused,
      });
    }
    for (const relationship of currentState.relationships) {
      if (!graph.hasNode(relationship.sourceArtistId) || !graph.hasNode(relationship.targetArtistId)) continue;
      graph.addUndirectedEdgeWithKey(relationship.id, relationship.sourceArtistId, relationship.targetArtistId, {
        type: "dotted",
        size: relationship.id === currentState.selectedRelationshipId ? 5.2 : 3.2,
        color: `rgba(${EDGE_COLORS[relationship.type]}, ${Math.max(0.3, Math.min(0.95, relationship.evidenceConfidence))})`,
      });
    }

    let renderer: Sigma | null = null;
    try {
      const narrowStage = container.clientWidth < 480;
      renderer = new Sigma(graph, container, {
        defaultEdgeType: "dotted",
        edgeProgramClasses: { dotted: DottedEdgeProgram },
        enableEdgeEvents: true,
        renderEdgeLabels: false,
        labelColor: { color: "#d7e2e2" },
        labelFont: "Inter, ui-sans-serif, system-ui, sans-serif",
        labelWeight: "500",
        labelSize: narrowStage ? 11 : 14,
        labelDensity: narrowStage ? 0.45 : 0.7,
        labelGridCellSize: narrowStage ? 140 : 110,
        labelRenderedSizeThreshold: 7,
        minCameraRatio: 0.65,
        maxCameraRatio: 2.8,
        stagePadding: 28,
        defaultDrawNodeLabel: drawContainedNodeLabel,
        defaultDrawNodeHover: drawContainedNodeLabel,
      });
      renderer.on("clickNode", ({ node }) => callbacksRef.current.onSelectArtist(node));
      renderer.on("clickEdge", ({ edge }) => callbacksRef.current.onSelectRelationship(edge));
      graphRef.current = graph;
      rendererRef.current = renderer;
      callbacksRef.current.onReady();
    } catch {
      renderer?.kill();
      callbacksRef.current.onUnavailable("unavailable");
      return;
    }

    const canvases = [...container.querySelectorAll("canvas")];
    const loseContext = (event: Event) => {
      event.preventDefault();
      callbacksRef.current.onUnavailable("context-lost");
    };
    for (const canvas of canvases) canvas.addEventListener("webglcontextlost", loseContext);

    return () => {
      for (const canvas of canvases) canvas.removeEventListener("webglcontextlost", loseContext);
      renderer?.kill();
      graph.clear();
      if (rendererRef.current === renderer) rendererRef.current = null;
      if (graphRef.current === graph) graphRef.current = null;
    };
  }, [artistKey, layout, locale]);

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      const graph = graphRef.current;
      const renderer = rendererRef.current;
      if (!graph || !renderer) return;
      for (const artist of artists) {
        if (!graph.hasNode(artist.id)) continue;
        const isFocused = artist.id === focusArtistId;
        const isRelated = !focusArtistId || relatedArtistIds.has(artist.id);
        graph.mergeNodeAttributes(artist.id, {
          color: isFocused ? "#f0dca8" : isRelated ? "#7fc4bd" : "#49595d",
          highlighted: isFocused,
        });
      }
      graph.clearEdges();
      for (const relationship of relationships) {
        if (!graph.hasNode(relationship.sourceArtistId) || !graph.hasNode(relationship.targetArtistId)) continue;
        graph.addUndirectedEdgeWithKey(relationship.id, relationship.sourceArtistId, relationship.targetArtistId, {
          type: "dotted",
          size: relationship.id === selectedRelationshipId ? 5.2 : 3.2,
          color: `rgba(${EDGE_COLORS[relationship.type]}, ${Math.max(0.3, Math.min(0.95, relationship.evidenceConfidence))})`,
        });
      }
      renderer.refresh();
    });
    return () => cancelAnimationFrame(frame);
  }, [artists, focusArtistId, relatedArtistIds, relationships, selectedRelationshipId]);

  return <div ref={containerRef} className="constellation-canvas" aria-hidden="true" />;
}
