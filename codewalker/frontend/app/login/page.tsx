const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export default function Login() {
  return (
    <main className="min-h-screen bg-black text-paper flex items-center justify-center">
      <a
        href={`${API_URL}/auth/github/login`}
        className="font-mono text-sm bg-signal text-panel px-6 py-3 rounded-[3px] hover:bg-signalBright transition-colors"
      >
        Continue with GitHub
      </a>
    </main>
  );
}
