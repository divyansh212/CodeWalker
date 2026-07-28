import { HexIcon } from "./HexIcon";

export function Footer() {
  return (
    <footer className="border-t border-hairlineSoft px-8 py-12 text-center">
      <div className="flex items-center justify-center gap-2 mb-2.5">
        <HexIcon className="w-[22px] h-[22px] text-signal" />
        <span className="font-display font-semibold text-[16px] text-paper">
          penguin<span className="font-mono font-normal text-signal">&gt;_</span>
        </span>
      </div>
      <p className="font-mono text-[13px] text-slateDim">AI agent for your codebase.</p>
    </footer>
  );
}
