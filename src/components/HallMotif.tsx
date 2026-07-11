export type HallId = "art" | "biology" | "music" | "games" | "civilization" | "science";

export function HallMotif({ hall }: { hall: HallId }) {
  return (
    <div className={`hall-motif hall-motif-${hall}`} aria-hidden="true">
      {hall === "art" && (
        <>
          <span className="art-frame" />
          <span className="art-stroke art-stroke-one" />
          <span className="art-stroke art-stroke-two" />
        </>
      )}
      {hall === "biology" && (
        <>
          <span className="bio-orbit bio-orbit-one" />
          <span className="bio-orbit bio-orbit-two" />
          <span className="bio-cell" />
        </>
      )}
      {hall === "music" && (
        <div className="sound-wave">
          {[30, 52, 76, 46, 88, 62, 38].map((height, index) => (
            <span key={`${height}-${index}`} style={{ "--wave-height": `${height}%` } as React.CSSProperties} />
          ))}
        </div>
      )}
      {hall === "games" && (
        <>
          <span className="game-path" />
          <span className="game-node game-node-a" />
          <span className="game-node game-node-b" />
          <span className="game-node game-node-c" />
        </>
      )}
      {hall === "civilization" && (
        <>
          <span className="city-layer city-layer-one" />
          <span className="city-layer city-layer-two" />
          <span className="city-sun" />
        </>
      )}
      {hall === "science" && (
        <>
          <span className="science-lens" />
          <span className="science-ray science-ray-one" />
          <span className="science-ray science-ray-two" />
          <span className="science-dot" />
        </>
      )}
    </div>
  );
}
