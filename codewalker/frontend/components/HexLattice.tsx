"use client";
import { useEffect, useRef } from "react";

function hexPoints(cx: number, cy: number, r: number) {
  const pts: string[] = [];
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 180) * (60 * i - 90);
    pts.push(`${(cx + r * Math.cos(angle)).toFixed(1)},${(cy + r * Math.sin(angle)).toFixed(1)}`);
  }
  return pts.join(" ");
}

export function HexLattice() {
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;

    function build() {
      if (!wrap) return;
      const width = (wrap.clientWidth || 900) * 1.2;
      const height = (wrap.clientHeight || 500) * 1.4;
      const r = 26;
      const hSpacing = Math.sqrt(3) * r;
      const vSpacing = 1.5 * r;
      const svgNS = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.setAttribute("preserveAspectRatio", "xMidYMin slice");
      svg.setAttribute(
        "style",
        "position:absolute;top:-8%;left:-8%;width:116%;height:140%;animation:hexDrift 70s linear infinite alternate;"
      );

      let rowIndex = 0;
      for (let y = -r; y < height + r; y += vSpacing) {
        const offsetX = rowIndex % 2 === 0 ? 0 : hSpacing / 2;
        for (let x = -r + offsetX; x < width + r; x += hSpacing) {
          const poly = document.createElementNS(svgNS, "polygon");
          poly.setAttribute("points", hexPoints(x, y, r));
          poly.setAttribute("fill", "none");
          poly.setAttribute("stroke", "#232228");
          poly.setAttribute("stroke-width", "1");
          svg.appendChild(poly);
        }
        rowIndex++;
      }

      wrap.innerHTML = "";
      wrap.appendChild(svg);
    }

    build();
    window.addEventListener("resize", build);
    return () => window.removeEventListener("resize", build);
  }, []);

  return (
    <div
      ref={wrapRef}
      className="absolute inset-0 overflow-hidden pointer-events-none opacity-50"
      style={{
        WebkitMaskImage: "radial-gradient(ellipse 90% 65% at 50% 0%, black 25%, transparent 88%)",
        maskImage: "radial-gradient(ellipse 90% 65% at 50% 0%, black 25%, transparent 88%)",
      }}
    />
  );
}
