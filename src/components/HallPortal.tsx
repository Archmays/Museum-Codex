import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { HallMotif, type HallId } from "./HallMotif";

export function HallPortal({ hall, featured = false }: { hall: HallId; featured?: boolean }) {
  const { t } = useI18n();
  const content = t.home.halls[hall];
  const inner = (
    <>
      <HallMotif hall={hall} />
      <div className="hall-copy">
        <div className="hall-heading-line">
          <p className="hall-kicker">{content.english}</p>
          <span className="hall-state"><span aria-hidden="true">{hall === "art" ? "✦" : "○"}</span>{content.status}</span>
        </div>
        <h3>{content.name}</h3>
        <p className="hall-description">{content.description}</p>
        {hall === "art" && (
          <span className="hall-enter">
            {t.common.open}
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13m-5-5 5 5-5 5" /></svg>
          </span>
        )}
      </div>
    </>
  );

  if (hall === "art") {
    return <Link className={`hall-portal ${featured ? "hall-featured" : ""}`} to="/art">{inner}</Link>;
  }

  return (
    <article className="hall-portal hall-closed" aria-label={`${content.name}，${content.status}`}>
      {inner}
    </article>
  );
}
