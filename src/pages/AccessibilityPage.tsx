import { PageIntro } from "../components/PageIntro";
import { useI18n } from "../i18n/I18nProvider";
import { usePreferences } from "../preferences/PreferencesProvider";

export function AccessibilityPage() {
  const { t } = useI18n();
  const { lowBandwidth, reducedMotion, toggleLowBandwidth } = usePreferences();
  return (
    <main id="main-content" className="inner-page accessibility-page" tabIndex={-1}>
      <PageIntro eyebrow={t.accessibility.eyebrow} title={t.accessibility.title} intro={t.accessibility.intro} />
      <section className="bandwidth-panel" aria-labelledby="bandwidth-title">
        <div className={`signal-visual ${lowBandwidth ? "signal-quiet" : ""}`} aria-hidden="true">
          <span /><span /><span /><span />
        </div>
        <div>
          <h2 id="bandwidth-title">{t.accessibility.bandwidthTitle}</h2>
          <p>{t.accessibility.bandwidthText}</p>
          <button className="primary-button" type="button" aria-pressed={lowBandwidth} onClick={toggleLowBandwidth}>
            {lowBandwidth ? t.accessibility.turnOff : t.accessibility.turnOn}
          </button>
          <p className="system-note" aria-live="polite">
            {lowBandwidth ? t.common.lowBandwidthOn : t.common.lowBandwidthOff}
            {reducedMotion ? " · prefers-reduced-motion" : ""}
          </p>
        </div>
      </section>
      <section className="access-list" aria-labelledby="features-title">
        <h2 id="features-title">{t.accessibility.featuresTitle}</h2>
        <ul>{t.accessibility.features.map((feature) => <li key={feature}>{feature}</li>)}</ul>
      </section>
      <section className="future-access">
        <p className="eyebrow">Equivalent paths</p>
        <h2>{t.accessibility.futureTitle}</h2>
        <p>{t.accessibility.futureText}</p>
      </section>
    </main>
  );
}
