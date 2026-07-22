import { useEffect, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { loadCurrentReleaseScope, type CurrentReleaseScope as ReleaseScope } from "../data/current-release-scope";

export function CurrentReleaseScope() {
  const { locale } = useI18n();
  const [scope, setScope] = useState<ReleaseScope | null>(null);

  useEffect(() => {
    let active = true;
    void loadCurrentReleaseScope().then((value) => { if (active) setScope(value); }, () => undefined);
    return () => { active = false; };
  }, []);

  if (!scope) return null;
  const zh = locale === "zh-CN";
  return (
    <section className="current-release-scope" aria-labelledby="current-release-scope-title" data-release-scope="verified">
      <div>
        <p className="eyebrow">{zh ? "当前公开馆藏" : "Current public collection"}</p>
        <h2 id="current-release-scope-title">{zh ? "从艺术家展厅到收藏页" : "From artist galleries to collection pages"}</h2>
        <p>{zh
          ? `${scope.selfHostedWorks} 件作品提供本站托管图片；${scope.externalLinkOnlyWorks} 件可前往馆藏机构查看；${scope.metadataOnlyWorks} 件保留完整资料而不以图片替代证据。`
          : `${scope.selfHostedWorks} works have site-hosted images; ${scope.externalLinkOnlyWorks} link to their holding institutions; ${scope.metadataOnlyWorks} retain complete records without substituting an image for evidence.`}</p>
      </div>
      <dl>
        <div><dt>{zh ? "艺术家" : "Artists"}</dt><dd>{scope.artists}</dd></div>
        <div><dt>{zh ? "作品" : "Artworks"}</dt><dd>{scope.artworks}</dd></div>
        <div><dt>{zh ? "艺术家展厅" : "Artist galleries"}</dt><dd>{scope.galleryProfiles}</dd></div>
        <div><dt>{zh ? "艺术家收藏页" : "Collection pages"}</dt><dd>{scope.collectionProfiles}</dd></div>
      </dl>
    </section>
  );
}
