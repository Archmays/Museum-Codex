import { PageIntro } from "../components/PageIntro";
import { useI18n } from "../i18n/I18nProvider";

export function AboutPage() {
  const { t } = useI18n();
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
        </div>
      </section>
    </main>
  );
}
