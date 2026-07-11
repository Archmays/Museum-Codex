export function PageIntro({ eyebrow, title, intro }: { eyebrow: string; title: string; intro: string }) {
  return (
    <header className="page-intro reveal-group">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p className="page-lede">{intro}</p>
    </header>
  );
}
