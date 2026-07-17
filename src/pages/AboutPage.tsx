import { Link } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { useI18n } from "../i18n/I18nProvider";

export function AboutPage() {
  const { locale, t } = useI18n();
  return (
    <main id="main-content" className="inner-page about-page" tabIndex={-1}>
      <PageIntro eyebrow={t.about.eyebrow} title={t.about.title} intro={t.about.intro} />
      <section className="principles" aria-label={t.about.title}>
        {t.about.principles.map(([title, body], index) => (
          <article key={title}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <h2>{title}</h2>
            <p>{body}</p>
          </article>
        ))}
      </section>
      <section className="rights-panel" aria-labelledby="rights-title">
        <div className="rights-mark" aria-hidden="true"><span>R</span></div>
        <div>
          <p className="eyebrow">{t.about.rightsEyebrow}</p>
          <h2 id="rights-title">{t.about.nowTitle}</h2>
          <p className="rights-primary">{t.about.nowText}</p>
          <p>{t.about.nowDetail}</p>
          <a className="text-link rights-notices-link" href={`${import.meta.env.BASE_URL}THIRD_PARTY_NOTICES.md`}>
            {t.constellation.noticesLink}
          </a>
          <a
            className="text-link rights-notices-link"
            href="https://github.com/Archmays/Museum-Codex/issues/new?template=rights-or-attribution.yml"
          >
            {t.constellation.rightsRequest}
          </a>
        </div>
      </section>
      <section className="rights-panel" aria-labelledby="map-method-title">
        <div className="rights-mark" aria-hidden="true"><span>⌖</span></div>
        <div>
          <p className="eyebrow">MUSEUM-07 · 1.3.0</p>
          <h2 id="map-method-title">{locale === "zh-CN" ? "地点是可核验的主张" : "Place is a verifiable claim"}</h2>
          <p className="rights-primary">{locale === "zh-CN" ? "艺术时空地图使用完全自托管的 Natural Earth 1:110m 自然地理轮廓与 Getty TGN 地点身份。" : "Art Across Time and Place uses fully self-hosted Natural Earth 1:110m physical outlines and Getty TGN place identities."}</p>
          <p>{locale === "zh-CN" ? "现代地图轮廓不等于历史政治边界；时间顺序不等于旅行路线；当前馆藏机构不等于创作地。" : "Modern outlines are not historical political borders; chronological order is not a travel route; a current holding institution is not a creation place."}</p>
          <Link className="text-link" to="/art/map">{locale === "zh-CN" ? "查看艺术时空地图" : "Open Art Across Time and Place"}</Link>
        </div>
      </section>
    </main>
  );
}
