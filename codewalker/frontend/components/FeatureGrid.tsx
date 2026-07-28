const FEATURES = [
  {
    title: "Reads the README",
    body: "Starts where a new hire would — what the project is, how it's structured, what it's for.",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round">
        <rect x="4" y="2.5" width="12" height="15" rx="1.5" />
        <line x1="7" y1="7" x2="13" y2="7" />
        <line x1="7" y1="10" x2="13" y2="10" />
        <line x1="7" y1="13" x2="10.5" y2="13" />
      </svg>
    ),
  },
  {
    title: "Walks the blame",
    body: "Attributes lines and functions to the people who actually wrote them, not just the last person to touch the file.",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round">
        <line x1="6" y1="3" x2="6" y2="10" />
        <circle cx="6" cy="3" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="6" cy="10" r="1.5" fill="currentColor" stroke="none" />
        <path d="M6 10 Q6 15.5 11 15.5 H12.4" />
        <circle cx="14" cy="15.5" r="1.5" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    title: "Builds a voice",
    body: "Commit tone, verbosity, the parts of the codebase someone kept coming back to — a rough signature per contributor.",
    icon: (
      <svg viewBox="0 0 20 20">
        <rect x="2.5" y="8" width="2" height="4" fill="currentColor" />
        <rect x="6.5" y="4" width="2" height="12" fill="currentColor" />
        <rect x="10.5" y="6" width="2" height="8" fill="currentColor" />
        <rect x="14.5" y="2.5" width="2" height="15" fill="currentColor" />
      </svg>
    ),
  },
  {
    title: "Answers in character",
    body: "Confusing legacy code gets explained in first person, in the inferred voice of whoever wrote it — not a generic summary.",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.4}>
        <rect x="2" y="3.5" width="16" height="9" rx="1.5" />
        <path d="M6.5 12.5 4.5 16.5 9 12.5Z" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    title: "Finds your first repo",
    body: "Tell it what you want to learn and it surfaces a repo and an issue that actually fit.",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.4} strokeLinecap="round">
        <circle cx="8.5" cy="8.5" r="5" />
        <line x1="12.2" y1="12.2" x2="17" y2="17" />
      </svg>
    ),
  },
  {
    title: "Gets you unstuck",
    body: "Stuck on an issue? It proposes a fix and walks you through it, step by step.",
    icon: (
      <svg
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="2.5" y="10" width="6" height="6" rx="1" />
        <path d="M9 10 15 4" />
        <path d="M10.5 4H15V8.5" />
      </svg>
    ),
  },
];

export function FeatureGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-hairlineSoft border border-hairlineSoft rounded-md overflow-hidden">
      {FEATURES.map((f) => (
        <div key={f.title} className="group bg-panel p-7">
          <div className="w-[38px] h-[38px] border border-hairline rounded-md flex items-center justify-center mb-4 text-slate group-hover:border-signal group-hover:text-signal transition-colors">
            <div className="w-[19px] h-[19px]">{f.icon}</div>
          </div>
          <h3 className="font-display font-semibold text-[15px] text-paper mb-2">{f.title}</h3>
          <p className="text-[13.5px] text-slate">{f.body}</p>
        </div>
      ))}
    </div>
  );
}
