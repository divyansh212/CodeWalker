const STEPS = [
  { num: "01", title: "Tell it what you want to learn", body: "Language, topic, how much time you've got this week." },
  { num: "02", title: "It finds a repo and an issue", body: "Something real and scoped, usually tagged good first issue." },
  { num: "03", title: "Stuck? It walks you through it", body: "Step by step, in plain language, without just handing you the diff." },
];

export function OssSteps() {
  return (
    <div className="flex flex-col">
      {STEPS.map((s, i) => (
        <div
          key={s.num}
          className={`flex gap-6 py-6 border-t border-hairlineSoft ${i === STEPS.length - 1 ? "border-b" : ""}`}
        >
          <span className="font-mono text-[13px] text-signal shrink-0 pt-0.5">{s.num}</span>
          <div>
            <h3 className="font-display font-semibold text-base text-paper mb-1.5">{s.title}</h3>
            <p className="text-sm text-slate">{s.body}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
