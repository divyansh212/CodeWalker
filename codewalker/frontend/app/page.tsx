import { Nav } from "@/components/Nav";
import { HexLattice } from "@/components/HexLattice";
import { HexIcon } from "@/components/HexIcon";
import { Terminal } from "@/components/Terminal";
import { FeatureGrid } from "@/components/FeatureGrid";
import { OssSteps } from "@/components/OssSteps";
import { Footer } from "@/components/Footer";
import { Reveal } from "@/components/Reveal";

export default function Home() {
  return (
    <main className="bg-black text-paper">
      <Nav />

      <Reveal>
        <section className="relative py-24 overflow-hidden">
          <HexLattice />
          <div className="relative max-w-[640px] mx-auto px-8 text-center">
            <div className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-signal mb-7">
              <HexIcon className="w-3.5 h-3.5" />
              <span>Half debugging tool, half seance</span>
            </div>
            <h1 className="font-display font-semibold text-4xl md:text-5xl leading-tight mb-5 tracking-tight">
              Your codebase has ghosts.
              <br />
              Penguin talks to them.
            </h1>
            <p className="text-base text-slate max-w-md mx-auto mb-9">
              Point it at a repo and it reads the README, the commit history, and the blame — then explains
              the confusing parts in the actual voice of whoever wrote them.
            </p>
            <div className="flex gap-3.5 justify-center flex-wrap">
              <a
                href="#terminal-demo"
                className="font-mono text-[13px] font-medium bg-signal text-panel px-5 py-[11px] rounded-[3px] hover:bg-signalBright hover:-translate-y-px transition-all"
              >
                Watch it think
              </a>
              <a
                href="/login"
                className="font-mono text-[13px] font-medium border border-hairline text-paper px-5 py-[11px] rounded-[3px] hover:border-signal hover:-translate-y-px transition-all"
              >
                Connect a repo
              </a>
            </div>
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section id="terminal-demo" className="max-w-[720px] mx-auto px-8 py-16">
          <p className="text-center font-mono text-xs uppercase tracking-wider text-slateDim mb-5">Method</p>
          <Terminal title="penguin — retry_handler.py" mode="demo" />
          <p className="text-center text-sm text-slateDim mt-4">
            Demo mode — try asking about a file, a bug, or a weird comment. Connect a real repo to hear from
            actual contributors.
          </p>
        </section>
      </Reveal>

      <Reveal>
        <section id="features" className="max-w-[1120px] mx-auto px-8 py-20">
          <h2 className="font-display font-semibold text-[26px] text-center mb-12 tracking-tight">
            What it actually does
          </h2>
          <FeatureGrid />
        </section>
      </Reveal>

      <Reveal>
        <section id="oss" className="max-w-[680px] mx-auto px-8 py-20">
          <h2 className="font-display font-semibold text-[26px] text-center mb-12 tracking-tight">
            Never opened a pull request? Start here.
          </h2>
          <OssSteps />
        </section>
      </Reveal>

      <Footer />
    </main>
  );
}
