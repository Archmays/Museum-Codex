import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { useI18n } from "../i18n/I18nProvider";
import { galleryCopy } from "../features/art-gallery/copy";
import { CurrentReleaseScope } from "../components/CurrentReleaseScope";

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
      <CurrentReleaseScope />
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
            <small>{locale === "zh-CN" ? "进入当前正式艺术家数字展厅、作品详情与双作比较。" : "Enter the current formal artist galleries, artwork details, and two-work comparison."}</small>
          </Link>
          <Link className="constellation-entry" to="/art/tours">
            <span>{locale === "zh-CN" ? "深度观察导览" : "Deep observation tours"}</span>
            <small>{locale === "zh-CN" ? "进入艺术家导览与固定主题导览。" : "Enter artist tours and fixed thematic tours."}</small>
          </Link>
          <Link className="constellation-entry" to="/art/compare">
            <span>{gallery.openCompare}</span>
            <small>{locale === "zh-CN" ? "并置两件正式作品，比较观察卡、透镜、来源与细节区域。" : "Place two formal works together with observation cards, lenses, sources, and detail regions."}</small>
          </Link>
          <Link className="constellation-entry" to="/art/paths">
            <span>{locale === "zh-CN" ? "AB 可解释关系路径" : "Explainable A–B pathways"}</span>
            <small>{locale === "zh-CN" ? "在当前正式数据中选择两位艺术家，查看最短与替代路径及逐边证据。" : "Choose two artists in current published data and inspect shortest and alternative paths with per-edge evidence."}</small>
          </Link>
          <Link className="constellation-entry" to="/art/map">
            <span>{locale === "zh-CN" ? "艺术时空地图" : "Art Across Time and Place"}</span>
            <small>{locale === "zh-CN" ? "以地图、时间线与地点表核验艺术家的来源支持地点；不绘制推断旅行路线。" : "Explore source-supported artist places through an equivalent map, timeline, and place table—without inferred travel routes."}</small>
          </Link>
          <Link className="constellation-entry" to="/art/search">
            <span>{locale === "zh-CN" ? "搜索美术馆" : "Search the art museum"}</span>
            <small>{locale === "zh-CN" ? "按名称、别名、转写与原语言标签查找公开艺术家、作品、导览、地点、关系和路径。" : "Find public artists, artworks, tours, places, relationships, and paths by label, alias, transliteration, or source language."}</small>
          </Link>
        </div>
      </aside>
      <Link className="text-link" to="/">← {t.common.backHome}</Link>
    </main>
  );
}
