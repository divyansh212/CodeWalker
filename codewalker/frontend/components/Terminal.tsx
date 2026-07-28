"use client";
import { useEffect, useRef, useState } from "react";

type Segment = { text: string; cite?: boolean };
type LineKind = "prompt" | "question" | "meta" | "answer";
type Line = { kind: LineKind; segments: Segment[] };

type TerminalProps = {
  title: string;
  mode: "demo" | "live";
  apiUrl?: string;
  token?: string;
  owner?: string;
  repoName?: string;
};

const RETRY_SEGMENTS: Segment[] = [
  {
    text:
      "Okay — this retry loop. The backoff is hardcoded to 8 seconds because the vendor's API started " +
      "silently rate-limiting us mid-incident, and I didn't trust anyone — including future me — to leave " +
      "a config value alone under pressure. ",
  },
  { text: "Their docs buried the real limit in a changelog note", cite: true },
  { text: ", so I picked a number that worked and moved on. Should've left a comment. Sorry, future me." },
];

const DEMO_RESPONSES: { match: string[]; ghost: string; segments: Segment[] }[] = [
  {
    match: ["regex", "pattern"],
    ghost: "Ghost of @dev-priya · 9 commits · 2020",
    segments: [
      {
        text:
          "This regex looks like a monster because it kind of is one — it's matching three different date " +
          "formats our CSV exports used before we standardized on ISO. ",
      },
      { text: "A support ticket from that quarter", cite: true },
      { text: " is basically fossilized in here. I know, I know." },
    ],
  },
  {
    match: ["async", "promise", "race"],
    ghost: "Ghost of @marcus-l · 27 commits · 2021–2023",
    segments: [
      {
        text:
          "That extra await isn't defensive paranoia, it's scar tissue. We had a race where the cache write " +
          "finished after the read, and users saw stale data for a few minutes during a demo. ",
      },
      { text: "Never wrote a test for it", cite: true },
      { text: ", just added the await and moved on with my life." },
    ],
  },
  {
    match: ["config", "env", "hardcod"],
    ghost: "Ghost of @mira-k · 41 commits · 2019–2021",
    segments: RETRY_SEGMENTS,
  },
  {
    match: ["test", "todo"],
    ghost: "Ghost of @unknown · squashed history, author unclear",
    segments: [
      {
        text:
          "Honestly, I can't tell you who wrote this TODO — the commit got squashed during a rebase and the " +
          "message just says 'wip'. ",
      },
      { text: "Whoever it was never came back for it", cite: true },
      { text: ". That's the job sometimes." },
    ],
  },
];

const FALLBACK: { ghost: string; segments: Segment[] } = {
  ghost: "Ghost of @sam-w · 63 commits · 2018–ongoing",
  segments: [
    {
      text:
        "I don't have a real repo wired up in this demo — but point Penguin at yours and this is exactly the " +
        "register it answers in: first person, grounded in the actual blame, not a guess. ",
    },
    { text: "Try asking about a regex, a race condition, or a hardcoded value", cite: true },
    { text: " to see it respond differently." },
  ],
};

function pickDemoResponse(text: string) {
  const lower = text.toLowerCase();
  for (const r of DEMO_RESPONSES) {
    if (r.match.some((m) => lower.includes(m))) return { ghost: r.ghost, segments: r.segments };
  }
  return FALLBACK;
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

const LINE_CLASS: Record<LineKind, string> = {
  prompt: "text-signal",
  question: "text-paper",
  meta: "text-slateDim text-[12px]",
  answer: "text-slate",
};

export function Terminal({ title, mode, apiUrl, token, owner, repoName }: TerminalProps) {
  const [lines, setLines] = useState<Line[]>([]);
  const [typing, setTyping] = useState<{ kind: LineKind; segments: Segment[]; visibleChars: number } | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [busy, setBusy] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  const sectionRef = useRef<HTMLDivElement>(null);
  const playedRef = useRef(false);

  function scrollToBottom() {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }

  async function typeLine(kind: LineKind, segments: Segment[], speed = 14) {
    const totalChars = segments.reduce((sum, s) => sum + s.text.length, 0);
    for (let i = 1; i <= totalChars; i++) {
      setTyping({ kind, segments, visibleChars: i });
      scrollToBottom();
      await sleep(speed);
    }
    setLines((prev) => [...prev, { kind, segments }]);
    setTyping(null);
  }

  async function playDemo() {
    await typeLine("prompt", [{ text: "> blame retry_handler.py:42" }], 22);
    await sleep(350);
    await typeLine("meta", [{ text: "Ghost of @mira-k · 41 commits · 2019–2021" }], 12);
    await sleep(250);
    await typeLine("answer", RETRY_SEGMENTS, 12);
  }

  useEffect(() => {
    if (mode !== "demo") return;
    const el = sectionRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !playedRef.current) {
            playedRef.current = true;
            playDemo();
            observer.disconnect();
          }
        });
      },
      { threshold: 0.4 }
    );
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  async function handleSubmit() {
    const value = inputValue.trim();
    if (!value || busy) return;
    setBusy(true);
    setInputValue("");

    await typeLine("question", [{ text: "> " + value }], 10);
    await sleep(250);

    if (mode === "demo") {
      const picked = pickDemoResponse(value);
      await typeLine("meta", [{ text: picked.ghost }], 10);
      await sleep(200);
      await typeLine("answer", picked.segments, 10);
    } else if (apiUrl && token && owner && repoName) {
      try {
        const res = await fetch(`${apiUrl}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ owner, name: repoName, message: value }),
        });
        const data = await res.json();
        await typeLine("answer", [{ text: data.response || "No response from the agent." }], 6);
      } catch {
        await typeLine("answer", [{ text: "Couldn't reach the backend — check that it's running." }], 6);
      }
    }
    setBusy(false);
  }

  function renderSegments(segments: Segment[], visibleChars?: number) {
    let consumed = 0;
    return segments.map((seg, i) => {
      let text = seg.text;
      if (visibleChars !== undefined) {
        const remaining = visibleChars - consumed;
        text = remaining <= 0 ? "" : seg.text.slice(0, remaining);
        consumed += seg.text.length;
      }
      return (
        <span key={i} className={seg.cite ? "text-signalBright" : undefined}>
          {text}
        </span>
      );
    });
  }

  const showInput = mode === "live" || lines.length > 0;

  return (
    <div ref={sectionRef} className="rounded-md border border-hairline bg-panel overflow-hidden">
      <div className="flex items-center gap-[7px] bg-panel2 border-b border-hairline px-4 py-[11px]">
        <span className="w-2 h-2 rounded-full bg-hairline" />
        <span className="w-2 h-2 rounded-full bg-hairline" />
        <span className="w-2 h-2 rounded-full bg-hairline" />
        <span className="font-mono text-[12px] text-slateDim ml-1.5">{title}</span>
      </div>

      <div
        ref={bodyRef}
        className="font-mono text-[13px] leading-[1.85] px-[22px] pt-[22px] pb-1.5 min-h-[180px] max-h-[360px] overflow-y-auto"
      >
        {lines.map((line, i) => (
          <div key={i} className={`mb-3.5 whitespace-pre-wrap break-words ${LINE_CLASS[line.kind]}`}>
            {renderSegments(line.segments)}
          </div>
        ))}
        {typing && (
          <div className={`mb-3.5 whitespace-pre-wrap break-words ${LINE_CLASS[typing.kind]}`}>
            {renderSegments(typing.segments, typing.visibleChars)}
            <span className="inline-block w-1.5 h-3.5 bg-signal align-middle animate-pulse" />
          </div>
        )}
      </div>

      {showInput && (
        <div className="flex items-center gap-2 px-[22px] py-3.5 border-t border-hairlineSoft">
          <span className="font-mono text-signal text-[13px]">&gt;</span>
          <input
            className="flex-1 bg-transparent outline-none font-mono text-[13px] text-paper placeholder:text-slateDim"
            placeholder={
              mode === "demo"
                ? "ask about a regex, a race condition, a hardcoded value…"
                : "ask about a file, a bug, a weird comment…"
            }
            value={inputValue}
            disabled={busy}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSubmit();
            }}
          />
        </div>
      )}
    </div>
  );
}
