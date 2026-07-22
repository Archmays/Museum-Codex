import { Link, useLocation } from "react-router-dom";
import { PageIntro } from "../components/PageIntro";
import { useI18n } from "../i18n/I18nProvider";
import { CurrentReleaseScope } from "../components/CurrentReleaseScope";

export function AboutPage() {
  const { locale, t } = useI18n();
  const location = useLocation();
  const rightsRoute = location.pathname === "/rights";
  return (
    <main id="main-content" className="inner-page about-page" tabIndex={-1}>
      <PageIntro
        eyebrow={rightsRoute ? (locale === "zh-CN" ? "权利、来源与撤回" : "Rights, sources, and withdrawal") : t.about.eyebrow}
        title={rightsRoute ? (locale === "zh-CN" ? "让每项资料都能回到边界与来源" : "Keep every item connected to its boundaries and sources") : t.about.title}
        intro={rightsRoute ? (locale === "zh-CN" ? "代码、原创文字、元数据与媒体各自保留独立权利状态；来源、署名、撤回和隐私入口始终可抵达。" : "Code, original writing, metadata, and media retain separate rights states; sources, attribution, withdrawal, and privacy remain reachable.") : t.about.intro}
      />
      <CurrentReleaseScope />
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
          <p className="eyebrow">{locale === "zh-CN" ? "地点方法" : "Place method"}</p>
          <h2 id="map-method-title">{locale === "zh-CN" ? "地点是可核验的主张" : "Place is a verifiable claim"}</h2>
          <p className="rights-primary">{locale === "zh-CN" ? "艺术时空地图使用完全自托管的 Natural Earth 1:110m 自然地理轮廓与 Getty TGN 地点身份。" : "Art Across Time and Place uses fully self-hosted Natural Earth 1:110m physical outlines and Getty TGN place identities."}</p>
          <p>{locale === "zh-CN" ? "现代地图轮廓不等于历史政治边界；时间顺序不等于旅行路线；当前馆藏机构不等于创作地。" : "Modern outlines are not historical political borders; chronological order is not a travel route; a current holding institution is not a creation place."}</p>
          <Link className="text-link" to="/art/map">{locale === "zh-CN" ? "查看艺术时空地图" : "Open Art Across Time and Place"}</Link>
        </div>
      </section>
      <section className="rights-panel" id="privacy" aria-labelledby="privacy-title">
        <div className="rights-mark" aria-hidden="true"><span>∅</span></div>
        <div>
          <p className="eyebrow">{locale === "zh-CN" ? "隐私" : "Privacy"}</p>
          <h2 id="privacy-title">{locale === "zh-CN" ? "不建立访客档案" : "No visitor profile"}</h2>
          <p className="rights-primary">{locale === "zh-CN" ? "没有 analytics、账户、查询历史、Cookie、指纹、用户定位或远程日志。" : "There is no analytics, account, query history, cookie, fingerprinting, user geolocation, or remote logging."}</p>
          <p>{locale === "zh-CN" ? "只在浏览器中保存你明确选择的语言与低带宽偏好；艺术家选择、作品比较、路径、地图筛选、导览访问和 print/share 历史均不保存。" : "Only explicit language and low-bandwidth preferences are kept in the browser. Artist selections, comparisons, paths, map filters, tour visits, and print/share history are not stored."}</p>
          <Link className="text-link" to="/art/search">{locale === "zh-CN" ? "打开无记录搜索" : "Open unlogged search"}</Link>
        </div>
      </section>
    </main>
  );
}
