import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { localize } from "../../art-constellation/types";
import { useI18n } from "../../../i18n/I18nProvider";
import type { ObservationCard as ObservationCardRecord } from "../interaction-types";
import { artworkPath } from "../media";

type ObservationCardProps = {
  card: ObservationCardRecord;
  compact?: boolean;
  headingLevel?: 2 | 3 | 4;
};

function CardSubheading({ level, id, children }: { level: 3 | 4 | 5; id?: string; children: ReactNode }) {
  if (level === 5) return <h5 id={id}>{children}</h5>;
  if (level === 4) return <h4 id={id}>{children}</h4>;
  return <h3 id={id}>{children}</h3>;
}

export function ObservationCard({ card, compact = false, headingLevel = 2 }: ObservationCardProps) {
  const { locale } = useI18n();
  const zh = locale === "zh-CN";
  const contextGroups = [
    [zh ? "材料" : "Materials", card.contexts.materials],
    [zh ? "技法" : "Techniques", card.contexts.techniques],
    [zh ? "题材" : "Subjects", card.contexts.subjects],
  ] as const;
  const heading = localize(card.title, locale);
  const subheadingLevel = (headingLevel + 1) as 3 | 4 | 5;
  const rightsLabel: Record<string, string> = {
    approved_self_hosted: zh ? "批准的本地发布图像" : "Approved self-hosted image",
    metadata_only_after_automated_review: zh ? "自动审核后的元数据路径" : "Metadata path after automated review",
    blocked_source_unavailable: zh ? "来源媒体不可用，保留元数据路径" : "Source media unavailable; metadata path retained",
    blocked_rights_conflict: zh ? "媒体权利冲突，保留元数据路径" : "Media rights conflict; metadata path retained",
  };
  return (
    <section className="observation-card" data-compact={compact ? "true" : "false"} aria-labelledby={`${card.id}-title`}>
      <header>
        <p className="eyebrow">{zh ? "结构化观察卡" : "Structured observation card"}</p>
        {headingLevel === 4
          ? <h4 id={`${card.id}-title`}>{heading}</h4>
          : headingLevel === 3
            ? <h3 id={`${card.id}-title`}>{heading}</h3>
            : <h2 id={`${card.id}-title`}>{heading}</h2>}
        <p className="observation-card-status">
          {card.image_availability === "approved_image"
            ? (zh ? "批准图像与文字路径" : "Approved image and text path")
            : (zh ? "完整元数据与证据路径" : "Complete metadata and evidence path")}
        </p>
      </header>

      <dl className="observation-card-metadata">
        <div><dt>{zh ? "年代" : "Date"}</dt><dd>{card.date ? localize(card.date, locale) : "—"}</dd></div>
        <div><dt>{zh ? "机构" : "Institution"}</dt><dd>{card.institution ? localize(card.institution, locale) : "—"}</dd></div>
        <div><dt>{zh ? "审核" : "Review"}</dt><dd>{zh ? `自动审核通过 · ${card.review.reviewed_at}` : `Automated review passed · ${card.review.reviewed_at}`}</dd></div>
      </dl>

      <ol className="observation-prompts">
        {card.prompts.map((prompt, index) => (
          <li key={`${card.id}-prompt-${index}`}><span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span><p>{localize(prompt, locale)}</p></li>
        ))}
      </ol>

      <div className="observation-contexts">
        {contextGroups.map(([label, entries]) => (
          <div key={label}><CardSubheading level={subheadingLevel}>{label}</CardSubheading><p>{entries.length ? entries.map((entry) => localize(entry.label, locale)).join(" · ") : "—"}</p></div>
        ))}
      </div>

      <div className="observation-boundaries">
        <section>
          <CardSubheading level={subheadingLevel}>{zh ? "可直接观察或核验" : "Directly observable or verifiable"}</CardSubheading>
          <ul>{card.directly_observable.map((item, index) => <li key={`${card.id}-direct-${index}`}>{localize(item, locale)}</li>)}</ul>
        </section>
        <section>
          <CardSubheading level={subheadingLevel}>{zh ? "解释需要来源" : "Interpretation needs sources"}</CardSubheading>
          <ul>{card.interpretation_requires_sources.map((item, index) => <li key={`${card.id}-source-${index}`}>{localize(item, locale)}</li>)}</ul>
        </section>
        <section>
          <CardSubheading level={subheadingLevel}>{zh ? "当前证据不能证明" : "Current evidence cannot prove"}</CardSubheading>
          <ul>{card.current_evidence_cannot_prove.map((item, index) => <li key={`${card.id}-limit-${index}`}>{localize(item, locale)}</li>)}</ul>
        </section>
      </div>
      <p className="observation-accessibility" role="note">{localize(card.accessibility_version.summary, locale)}</p>
      <div className="observation-reference-links">
        <section aria-labelledby={`${card.id}-evidence-title`}>
          <CardSubheading level={subheadingLevel} id={`${card.id}-evidence-title`}>{zh ? "证据链接" : "Evidence links"}</CardSubheading>
          <ul>{card.evidence_ids.map((id) => <li key={id}><Link to={artworkPath(card.artwork_id)}>{id}</Link></li>)}</ul>
        </section>
        <section aria-labelledby={`${card.id}-source-title`}>
          <CardSubheading level={subheadingLevel} id={`${card.id}-source-title`}>{zh ? "来源链接" : "Source links"}</CardSubheading>
          <ul>{card.source_links.map((source) => <li key={source.source_id}><a href={source.url} rel="noreferrer">{localize(source.label, locale)} · {source.source_id}</a></li>)}</ul>
        </section>
      </div>
      <footer>
        <span>{card.release_id} · {card.release_version}</span>
        <span>{locale === "zh-CN" ? "权利状态" : "Rights"}: {rightsLabel[card.rights_status] ?? card.rights_status}</span>
      </footer>
    </section>
  );
}
