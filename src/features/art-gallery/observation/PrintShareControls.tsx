import { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useI18n } from "../../../i18n/I18nProvider";

type PrintShareControlsProps = {
  releaseId: string;
  releaseVersion: string;
  state?: Record<string, string | null | undefined>;
};

export function PrintShareControls({ releaseId, releaseVersion, state = {} }: PrintShareControlsProps) {
  const { locale } = useI18n();
  const location = useLocation();
  const [status, setStatus] = useState("");
  const params = useMemo(() => {
    const value = new URLSearchParams();
    for (const [key, entry] of Object.entries(state)) if (entry) value.set(key, entry);
    return value;
  }, [state]);
  const printParams = new URLSearchParams(params);
  printParams.set("view", "print");
  const printTarget = `${location.pathname}?${printParams.toString()}`;
  const canonicalUrl = typeof window === "undefined"
    ? `#${location.pathname}${params.size ? `?${params}` : ""}`
    : `${window.location.origin}${window.location.pathname}#${location.pathname}${params.size ? `?${params}` : ""}`;
  const isPrintView = new URLSearchParams(location.search).get("view") === "print";
  const copyUrl = async () => {
    try {
      await navigator.clipboard.writeText(canonicalUrl);
      setStatus(locale === "zh-CN" ? "不含跟踪参数的页面 URL 已复制。" : "The tracking-free page URL was copied.");
    } catch {
      setStatus(locale === "zh-CN" ? "请从下方复制页面 URL。" : "Copy the page URL shown below.");
    }
  };
  return (
    <aside className="print-share-controls" aria-label={locale === "zh-CN" ? "打印与分享" : "Print and share"}>
      <div className="print-share-actions">
        {isPrintView
          ? <button type="button" onClick={() => window.print()}>{locale === "zh-CN" ? "打印此页" : "Print this page"}</button>
          : <Link to={printTarget}>{locale === "zh-CN" ? "打开打印视图" : "Open print view"}</Link>}
        <button type="button" onClick={() => void copyUrl()}>{locale === "zh-CN" ? "复制分享链接" : "Copy share link"}</button>
      </div>
      <p className="print-share-url">{canonicalUrl}</p>
      <p className="print-share-release" data-release-id={releaseId}><span>{locale === "zh-CN" ? "公开数据版本" : "Public data version"}</span> <span>{releaseVersion}</span></p>
      <p aria-live="polite">{status}</p>
    </aside>
  );
}
