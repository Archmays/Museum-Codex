import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  locale: "zh-CN" | "en";
};

type State = {
  failed: boolean;
};

export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error("Route chunk failed", error, info.componentStack);
    }
  }

  render() {
    if (!this.state.failed) return this.props.children;
    const zh = this.props.locale === "zh-CN";
    return (
      <main id="main-content" className="inner-page route-error" tabIndex={-1}>
        <p className="eyebrow">{zh ? "静态韧性" : "Static resilience"}</p>
        <h1>{zh ? "这一部分暂时没有完整载入" : "This part did not load completely"}</h1>
        <p className="page-lede" role="alert">
          {zh
            ? "路由文件中断；其他文字入口仍可使用。"
            : "The route file was interrupted; other text routes remain available."}
        </p>
        <div className="route-error-actions">
          <button type="button" className="primary-button" onClick={() => window.location.reload()}>
            {zh ? "重试当前页面" : "Retry this page"}
          </button>
          <a className="text-link" href="#/art">{zh ? "返回艺术序厅" : "Back to Art foyer"}</a>
        </div>
      </main>
    );
  }
}
