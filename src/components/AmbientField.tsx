export function AmbientField() {
  return (
    <div className="ambient-field" aria-hidden="true">
      <div className="ambient-glow ambient-glow-one" />
      <div className="ambient-glow ambient-glow-two" />
      <svg className="constellation" viewBox="0 0 1200 760" preserveAspectRatio="xMidYMid slice">
        <path d="M52 524C238 419 295 142 518 214s238 373 450 263 132-295 202-353" />
        <path d="M102 158c152 16 184 188 328 203s205-96 310-47 129 230 339 209" />
        <path d="M164 650c163-102 250 32 389-57s248-188 475-81" />
        {[
          [102, 158], [228, 272], [430, 361], [518, 214], [688, 336], [844, 491],
          [968, 477], [1079, 523], [164, 650], [553, 593], [1028, 512], [1148, 164],
        ].map(([cx, cy], index) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={index % 3 === 0 ? 4 : 2.5} />
        ))}
      </svg>
    </div>
  );
}
