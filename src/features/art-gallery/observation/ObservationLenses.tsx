import { Link } from "react-router-dom";
import { useI18n } from "../../../i18n/I18nProvider";
import { localize } from "../../art-constellation/types";
import { artworkPath } from "../media";
import type { ObservationLens } from "../interaction-types";

type ObservationLensesProps = {
  lenses: ObservationLens[];
  artworkIds: string[];
  activeLens?: ObservationLens["type"] | null;
  onLensChange?: (lens: ObservationLens["type"] | null) => void;
};

export function ObservationLenses({ lenses, artworkIds, activeLens = null, onLensChange }: ObservationLensesProps) {
  const { locale } = useI18n();
  const selected = new Set(artworkIds);
  return (
    <section className="observation-lenses" aria-labelledby="observation-lenses-title">
      <p className="eyebrow">{locale === "zh-CN" ? "观察透镜" : "Observation lenses"}</p>
      <h2 id="observation-lenses-title">{locale === "zh-CN" ? "从正式语境切换观看问题" : "Change the question through reviewed contexts"}</h2>
      {onLensChange ? (
        <div className="observation-lens-switcher" aria-label={locale === "zh-CN" ? "选择比较透镜" : "Choose a comparison lens"}>
          {lenses.map((lens) => <button key={lens.id} type="button" aria-pressed={activeLens === lens.type} onClick={() => onLensChange(activeLens === lens.type ? null : lens.type)}>{localize(lens.title, locale)}</button>)}
        </div>
      ) : null}
      <div className="observation-lens-grid">
        {lenses.map((lens) => {
          const entries = lens.entries.filter((entry) => entry.artwork_ids.some((id) => selected.has(id)));
          return (
            <details key={lens.id} open={activeLens ? activeLens === lens.type : artworkIds.length === 1}>
              <summary>{localize(lens.title, locale)} <span>{entries.length}</span></summary>
              <p>{localize(lens.boundary, locale)}</p>
              {entries.length ? (
                <ul>
                  {entries.map((entry) => (
                    <li key={entry.context_id}>
                      <h3>{localize(entry.label, locale)}</h3>
                      <p>{localize(entry.definition, locale)}</p>
                      <div className="lens-related-links">
                        {entry.artwork_ids.filter((id) => !selected.has(id)).slice(0, 4).map((id) => <Link key={id} to={artworkPath(id)}>{id}</Link>)}
                      </div>
                      <dl className="lens-reference-list">
                        <div><dt>{locale === "zh-CN" ? "证据" : "Evidence"}</dt><dd>{entry.evidence_ids.map((id) => <Link key={id} to={artworkPath(entry.artwork_ids[0])}>{id}</Link>)}</dd></div>
                        <div><dt>{locale === "zh-CN" ? "来源" : "Sources"}</dt><dd>{entry.source_links.map((source) => <a key={source.source_id} href={source.url} rel="noreferrer">{localize(source.label, locale)} · {source.source_id}</a>)}</dd></div>
                      </dl>
                    </li>
                  ))}
                </ul>
              ) : <p>—</p>}
            </details>
          );
        })}
      </div>
    </section>
  );
}
