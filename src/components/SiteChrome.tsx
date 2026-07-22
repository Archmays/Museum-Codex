import { NavLink, useLocation } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { usePreferences } from "../preferences/PreferencesProvider";
import { AmbientField } from "./AmbientField";
import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";

export function SiteChrome({ children }: { children: ReactNode }) {
  const { locale, setLocale, t } = useI18n();
  const { lowBandwidth, toggleLowBandwidth } = usePreferences();
  const { pathname } = useLocation();
  const previousPathname = useRef(pathname);
  const [routeAnnouncement, setRouteAnnouncement] = useState("");

  useEffect(() => {
    const routeChanged = previousPathname.current !== pathname;
    previousPathname.current = pathname;
    let innerFrame = 0;
    const outerFrame = requestAnimationFrame(() => {
      innerFrame = requestAnimationFrame(() => {
        const main = document.getElementById("main-content");
        const label = main?.querySelector("h1")?.textContent?.trim() || t.meta.siteName;
        document.title = `${label} · ${t.meta.siteName}`;
        if (routeChanged) {
          setRouteAnnouncement(locale === "zh-CN" ? `已打开：${label}` : `Opened: ${label}`);
          main?.focus({ preventScroll: true });
          main?.scrollIntoView?.({ block: "start" });
        }
      });
    });
    return () => {
      cancelAnimationFrame(outerFrame);
      cancelAnimationFrame(innerFrame);
    };
  }, [locale, pathname, t.meta.siteName]);

  const skipToMain = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    const main = document.getElementById("main-content");
    main?.focus({ preventScroll: true });
    main?.scrollIntoView?.({ block: "start" });
  };

  return (
    <div className="site-shell">
      <AmbientField />
      <a className="skip-link" href="#main-content" onClick={skipToMain}>{t.common.skip}</a>
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">{routeAnnouncement}</p>
      <div className="print-masthead" aria-hidden="true">
        <strong>{t.meta.siteName} · {t.meta.siteNameEnglish}</strong>
      </div>
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
          <NavLink to="/art/search">{locale === "zh-CN" ? "搜索" : "Search"}</NavLink>
          <NavLink to="/about">{t.common.about}</NavLink>
          <NavLink to="/accessibility">{t.common.accessibility}</NavLink>
          <details className="art-nav-menu">
            <summary>{locale === "zh-CN" ? "探索" : "Explore"}</summary>
            <nav aria-label={t.common.menu}>
              <NavLink to="/art/constellation">{locale === "zh-CN" ? "关系探索" : "Connections"}</NavLink>
              <NavLink to="/art/artists">{locale === "zh-CN" ? "艺术家" : "Artists"}</NavLink>
              <NavLink to="/art/compare">{locale === "zh-CN" ? "作品比较" : "Compare"}</NavLink>
              <NavLink to="/art/tours">{locale === "zh-CN" ? "深度导览" : "Tours"}</NavLink>
              <NavLink to="/art/paths">{locale === "zh-CN" ? "A–B 路径" : "A–B paths"}</NavLink>
              <NavLink to="/art/map">{locale === "zh-CN" ? "时空地图" : "Time/place"}</NavLink>
            </nav>
          </details>
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
          <NavLink to="/rights">{locale === "zh-CN" ? "权利与来源" : "Rights & sources"}</NavLink>
          <NavLink to="/about">{t.common.about}</NavLink>
          <NavLink to="/accessibility">{t.common.accessibility}</NavLink>
        </nav>
      </footer>
    </div>
  );
}
