import type { Locale } from "../../i18n/translations";
import { localize, type LayoutNode } from "../art-constellation/types";
import type { ArtistPath, PathArtist, PathRelationship } from "./types";

type PathGraphViewProps = {
  artists: PathArtist[];
  relationships: PathRelationship[];
  layout: LayoutNode[];
  path: ArtistPath;
  locale: Locale;
};

export function PathGraphView({ artists, relationships, layout, path, locale }: PathGraphViewProps) {
  const position = new Map(layout.map((node) => [node.artistId, node]));
  const artistById = new Map(artists.map((artist) => [artist.id, artist]));
  const pathEdges = new Set(path.relationship_ids);
  const pathNodes = new Set(path.artist_ids);
  const orderById = new Map(path.artist_ids.map((id, index) => [id, index + 1]));
  return (
    <figure className="path-graph" aria-labelledby="path-graph-caption">
      <svg viewBox="0 0 1000 1000" role="img" aria-labelledby="path-graph-title path-graph-description">
        <title id="path-graph-title">{locale === "zh-CN" ? "当前艺术家路径图" : "Current artist pathway graph"}</title>
        <desc id="path-graph-description">
          {locale === "zh-CN"
            ? "高亮边与编号节点构成当前路径；其余节点和关系保留但降低对比度。下方有完整文字等价内容。"
            : "Highlighted edges and numbered nodes form the current path; other nodes and relations remain dimmed. Full text-equivalent content follows."}
        </desc>
        <defs>
          <marker id="path-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" />
          </marker>
        </defs>
        <g className="path-graph-edges">
          {relationships.map((edge) => {
            const source = position.get(edge.source_artist_id);
            const target = position.get(edge.target_artist_id);
            if (!source || !target) return null;
            const active = pathEdges.has(edge.id);
            return (
              <line
                key={edge.id}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                className={active ? "is-path" : "is-context"}
                data-level={edge.level}
                markerEnd={active && edge.directed ? "url(#path-arrow)" : undefined}
              />
            );
          })}
        </g>
        <g className="path-graph-nodes">
          {layout.map((node) => {
            const artist = artistById.get(node.artistId);
            if (!artist) return null;
            const active = pathNodes.has(node.artistId);
            const order = orderById.get(node.artistId);
            return (
              <g key={node.artistId} transform={`translate(${node.x} ${node.y})`} className={active ? "is-path" : "is-context"}>
                <circle r="24" />
                {order ? <text className="path-node-order" y="7" textAnchor="middle">{order}</text> : null}
                <text className="path-node-label" y="48" textAnchor="middle">{localize(artist.labels, locale)}</text>
              </g>
            );
          })}
        </g>
      </svg>
      <figcaption id="path-graph-caption">
        {locale === "zh-CN" ? "节点大小固定；位置与中心性不表示价值。C 级边保持点线。" : "Node size is fixed; position and centrality do not express value. C-level edges remain dotted."}
      </figcaption>
    </figure>
  );
}
