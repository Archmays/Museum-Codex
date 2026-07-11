import { NavLink } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { usePreferences } from "../preferences/PreferencesProvider";
import { AmbientField } from "./AmbientField";
import type { MouseEvent, ReactNode } from "react";

export function SiteChrome({ children }: { children: ReactNode }) {
  const { locale, setLocale, t } = useI18n();
  const { lowBandwidth, toggleLowBandwidth } = usePreferences();

  const skipToMain = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    const main = document.getElementById("main-content");
    main?.focus({ preventScroll: true });
    main?.scrollIntoView({ block: "start" });
  };

  return (
    <div className="site-shell">
      <AmbientField />
      <a className="skip-link" href="#main-content" onClick={skipToMain}>{t.common.skip}</a>
      <header className="site-header">
        <NavLink className="brand" to="/" aria-label={`${t.meta.siteName} ${t.common.home}`}>
          <span className="brand-mark" aria-hidden="true"><span /></span>
          <span>
            <strong>{t.meta.siteName}</strong>
            <small>{t.meta.siteNameEnglish}</small>
          </span>
        </NavLink>
        <nav className="primary-nav" aria-label={t.common.menu}>
          <NavLink to="/" end>{t.common.home}</NavLink>
          <NavLink to="/art">{t.common.art}</NavLink>
          <NavLink to="/about">{t.common.about}</NavLink>
          <NavLink to="/accessibility">{t.common.accessibility}</NavLink>
        </nav>
        <div className="header-tools">
          <div className="language-switch" aria-label={t.common.language}>
            <button type="button" aria-pressed={locale === "zh-CN"} onClick={() => setLocale("zh-CN")}>中</button>
            <button type="button" aria-pressed={locale === "en"} onClick={() => setLocale("en")}>EN</button>
          </div>
          <button
            className="bandwidth-button"
            type="button"
            aria-pressed={lowBandwidth}
            title={lowBandwidth ? t.common.lowBandwidthOn : t.common.lowBandwidthOff}
            onClick={toggleLowBandwidth}
          >
            <span className="bandwidth-glyph" aria-hidden="true"><i /><i /><i /></span>
            <span>{t.common.lowBandwidth}</span>
          </button>
        </div>
      </header>
      {children}
      <footer className="site-footer">
        <div>
          <strong>{t.meta.siteName} · {t.meta.siteNameEnglish}</strong>
          <p>{t.common.rightsShort}</p>
        </div>
        <nav aria-label={t.common.menu}>
          <NavLink to="/about">{t.common.about}</NavLink>
          <NavLink to="/accessibility">{t.common.accessibility}</NavLink>
        </nav>
      </footer>
    </div>
  );
}
