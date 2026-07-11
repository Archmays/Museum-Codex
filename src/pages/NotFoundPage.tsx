import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";

export function NotFoundPage() {
  const { t } = useI18n();
  return (
    <main id="main-content" className="inner-page not-found-page" tabIndex={-1}>
      <p className="eyebrow">404</p>
      <h1>{t.notFound.title}</h1>
      <p>{t.notFound.text}</p>
      <Link className="primary-button link-button" to="/">{t.common.backHome}</Link>
    </main>
  );
}
