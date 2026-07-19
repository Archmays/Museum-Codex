import { PageIntro } from "../components/PageIntro";
import { useI18n } from "../i18n/I18nProvider";
import { usePreferences } from "../preferences/PreferencesProvider";

export function AccessibilityPage() {
  const { locale, t } = useI18n();
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
      <section className="future-access" aria-labelledby="privacy-access-title">
        <p className="eyebrow">Privacy by default</p>
        <h2 id="privacy-access-title">{locale === "zh-CN" ? "偏好帮助访问，不记录参观" : "Preferences aid access without recording visits"}</h2>
        <p>{locale === "zh-CN" ? "只保存语言与低带宽偏好；不保存搜索或访问，也不使用 analytics、Cookie、指纹或定位。" : "Only language and low-bandwidth preferences are stored; searches and visits are not, and there is no analytics, cookie, fingerprinting, or geolocation."}</p>
      </section>
    </main>
  );
}
