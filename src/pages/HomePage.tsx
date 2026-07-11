import { HallPortal } from "../components/HallPortal";
import { useI18n } from "../i18n/I18nProvider";

export function HomePage() {
  const { t } = useI18n();
  return (
    <main id="main-content" tabIndex={-1}>
      <section className="hero" aria-labelledby="home-title">
        <div className="hero-index" aria-hidden="true"><span>六馆</span><i /></div>
        <div className="hero-copy reveal-group">
          <p className="eyebrow">{t.home.eyebrow}</p>
          <h1 id="home-title">{t.home.title}</h1>
          <p className="hero-intro">{t.home.intro}</p>
          <p className="hero-lead">{t.home.lead}</p>
        </div>
        <div className="hero-orbit" aria-hidden="true">
          <span className="orbit-ring orbit-ring-one" />
          <span className="orbit-ring orbit-ring-two" />
          <span className="orbit-core"><i /></span>
          <span className="orbit-label orbit-label-art">ART</span>
          <span className="orbit-label orbit-label-life">LIFE</span>
          <span className="orbit-label orbit-label-sound">SOUND</span>
        </div>
      </section>

      <section className="halls-section" aria-labelledby="halls-title">
        <header className="section-heading">
          <p className="eyebrow">{t.home.sectionLabel}</p>
          <h2 id="halls-title">{t.home.sectionTitle}</h2>
          <p>{t.home.sectionIntro}</p>
        </header>
        <div className="hall-grid">
          <HallPortal hall="art" featured />
          <HallPortal hall="biology" />
          <HallPortal hall="music" />
          <HallPortal hall="games" />
          <HallPortal hall="civilization" />
          <HallPortal hall="science" />
        </div>
      </section>

      <section className="coda" aria-labelledby="coda-title">
        <span className="coda-line" aria-hidden="true" />
        <div>
          <p className="eyebrow">01 — 06</p>
          <h2 id="coda-title">{t.home.codaTitle}</h2>
        </div>
        <p>{t.home.codaText}</p>
      </section>
    </main>
  );
}
