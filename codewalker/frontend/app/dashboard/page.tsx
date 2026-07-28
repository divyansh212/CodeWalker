"use client";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Nav } from "@/components/Nav";
import { Terminal } from "@/components/Terminal";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

function DashboardInner() {
  const searchParams = useSearchParams();
  const [token, setToken] = useState<string | null>(null);
  const [owner, setOwner] = useState("");
  const [repoName, setRepoName] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const fromUrl = searchParams.get("token");
    if (fromUrl) {
      setToken(fromUrl);
      window.localStorage.setItem("codewalker_token", fromUrl);
    } else {
      const stored = window.localStorage.getItem("codewalker_token");
      if (stored) setToken(stored);
    }
  }, [searchParams]);

  async function connectRepo() {
    if (!token || !owner || !repoName) return;
    setConnected(true);
    setStatus("ingesting");
    await fetch(`${API_URL}/repos`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ owner, name: repoName }),
    });
    poll();
  }

  function poll() {
    const interval = setInterval(async () => {
      const res = await fetch(`${API_URL}/repos/${owner}/${repoName}/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data.status);
        if (data.status === "ready" || data.status === "error") clearInterval(interval);
      }
    }, 3000);
  }

  if (!token) {
    return (
      <main className="min-h-screen bg-black text-paper flex items-center justify-center font-mono text-slate">
        Not signed in.
        <a href="/login" className="text-signal ml-2">
          Sign in with GitHub
        </a>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-black text-paper">
      <Nav />
      <div className="max-w-[680px] mx-auto px-8 py-16">
        {!connected ? (
          <div className="space-y-4">
            <h1 className="font-display font-semibold text-2xl mb-6">Connect a repo</h1>
            <input
              className="w-full bg-panel border border-hairline rounded-[3px] px-4 py-3 font-mono text-sm text-paper outline-none focus:border-signal"
              placeholder="owner (e.g. facebook)"
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
            />
            <input
              className="w-full bg-panel border border-hairline rounded-[3px] px-4 py-3 font-mono text-sm text-paper outline-none focus:border-signal"
              placeholder="repo (e.g. react)"
              value={repoName}
              onChange={(e) => setRepoName(e.target.value)}
            />
            <button
              onClick={connectRepo}
              className="font-mono text-sm bg-signal text-panel px-5 py-3 rounded-[3px] hover:bg-signalBright transition-colors"
            >
              Ingest repo
            </button>
          </div>
        ) : status !== "ready" ? (
          <p className="font-mono text-sm text-slate">
            {status === "error"
              ? "Ingestion failed — check the backend logs."
              : "Reading the README, the commits, the blame…"}
          </p>
        ) : (
          <Terminal
            title={`penguin — ${owner}/${repoName}`}
            mode="live"
            apiUrl={API_URL}
            token={token}
            owner={owner}
            repoName={repoName}
          />
        )}
      </div>
    </main>
  );
}

export default function Dashboard() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-black" />}>
      <DashboardInner />
    </Suspense>
  );
}
