import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { useI18n } from "../i18n/I18nProvider";
import { galleryCopy } from "../features/art-gallery/copy";

export function ArtFoyerPage() {
  const { locale, t } = useI18n();
  const gallery = galleryCopy[locale];
  return (
    <main id="main-content" className="inner-page art-foyer" tabIndex={-1}>
      <PageIntro eyebrow={t.art.eyebrow} title={t.art.title} intro={t.art.intro} />
      <div className="foyer-composition" aria-hidden="true">
        <span className="foyer-frame foyer-frame-one" />
        <span className="foyer-frame foyer-frame-two" />
        <span className="foyer-axis" />
        <span className="foyer-point" />
      </div>
      <p className="foyer-body">{t.art.body}</p>
      <section className="approaches" aria-labelledby="approaches-title">
        <h2 id="approaches-title">{t.art.approachesTitle}</h2>
        <ol>
          {t.art.approaches.map(([title, description], index) => (
            <li key={title}>
              <span className="approach-number">{String(index + 1).padStart(2, "0")}</span>
              <div><h3>{title}</h3><p>{description}</p></div>
            </li>
          ))}
        </ol>
      </section>
      <aside className="empty-notice">
        <div className="notice-symbol" aria-hidden="true"><span /></div>
        <div>
          <h2>{t.art.noticeTitle}</h2>
          <p>{t.art.noticeText}</p>
          <Link className="constellation-entry" to="/art/constellation">
            <span>{t.art.constellationLink}</span>
            <small>{t.art.constellationLinkHint}</small>
          </Link>
          <Link className="constellation-entry" to="/art/artists">
            <span>{gallery.artistIndex}</span>
            <small>{locale === "zh-CN" ? "进入十二位艺术家的数字展厅、作品详情与双作比较。" : "Enter twelve artist galleries, artwork details, and two-work comparison."}</small>
          </Link>
        </div>
      </aside>
      <Link className="text-link" to="/">← {t.common.backHome}</Link>
    </main>
  );
}
