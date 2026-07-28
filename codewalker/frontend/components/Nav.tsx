"use client";
import { useEffect, useState } from "react";
import { HexIcon } from "./HexIcon";

export function Nav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      className={`sticky top-0 z-50 bg-black transition-colors border-b ${
        scrolled ? "border-hairline" : "border-transparent"
      }`}
    >
      <div className="max-w-[1120px] mx-auto flex items-center justify-between px-8 py-[18px]">
        <div className="flex items-center gap-2">
          <HexIcon className="w-[22px] h-[22px] text-signal" />
          <span className="font-display font-semibold text-[16px] text-paper">
            penguin<span className="font-mono font-normal text-signal">&gt;_</span>
          </span>
        </div>
        <div className="hidden md:flex gap-7 font-mono text-[13px] text-slate">
          <a href="#terminal-demo" className="hover:text-paper transition-colors">Method</a>
          <a href="#features" className="hover:text-paper transition-colors">Features</a>
          <a href="#oss" className="hover:text-paper transition-colors">Open source</a>
        </div>
        <a
          href="/login"
          className="font-mono text-[12px] bg-signal text-panel px-4 py-[9px] rounded-[3px] hover:bg-signalBright transition-colors"
        >
          Connect a repo
        </a>
      </div>
    </nav>
  );
}
