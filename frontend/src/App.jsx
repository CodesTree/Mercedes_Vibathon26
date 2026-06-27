import { useEffect, useState } from "react";

import { getApiBaseUrl, getHealth, runApiChecks } from "./api";


function App() {
  const [health, setHealth] = useState("checking");
  const [error, setError] = useState("");
  const [checks, setChecks] = useState([]);
  const [isChecking, setIsChecking] = useState(false);

  async function loadData() {
    setError("");
    try {
      const healthResponse = await getHealth();
      setHealth(healthResponse.status);
    } catch (requestError) {
      setHealth("offline");
      setError(requestError.message);
    }
  }

  async function loadChecks() {
    setIsChecking(true);
    try {
      setChecks(await runApiChecks());
    } finally {
      setIsChecking(false);
    }
  }

  useEffect(() => {
    loadData();
    loadChecks();
  }, []);

  const isOnline = health === "ok";
  const passing = checks.filter((check) => check.ok).length;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-50">
      <section className="mx-auto flex min-h-screen w-full max-w-5xl flex-col justify-center px-6 py-10">
        <div className="mb-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-cyan-300">
            CI/CD starter
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-normal sm:text-5xl">
            React frontend, FastAPI backend, one automated path to deploy.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-300">
            This boilerplate gives your team a clean starting point for pull
            requests, browser tests, Vercel deployment, and Render deployment.
          </p>
        </div>

        <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Backend status</h2>
            <span
              className={`h-3 w-3 rounded-full ${
                isOnline ? "bg-emerald-400" : "bg-rose-400"
              }`}
              aria-label={isOnline ? "API online" : "API offline"}
            />
          </div>
          <dl className="mt-5 space-y-3 text-sm">
            <div>
              <dt className="text-zinc-400">Health</dt>
              <dd className="mt-1 font-mono text-zinc-100">{health}</dd>
            </div>
            <div>
              <dt className="text-zinc-400">API base URL</dt>
              <dd className="mt-1 break-all font-mono text-zinc-100">
                {getApiBaseUrl()}
              </dd>
            </div>
          </dl>
          {error ? (
            <p className="mt-4 rounded-md border border-rose-400/40 bg-rose-400/10 px-3 py-2 text-sm text-rose-100">
              {error}
            </p>
          ) : null}
          <button
            type="button"
            onClick={loadData}
            className="mt-6 inline-flex h-10 items-center rounded-md bg-cyan-400 px-4 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-200 focus:ring-offset-2 focus:ring-offset-zinc-900"
          >
            Refresh API
          </button>
        </section>

        <section className="mt-4 rounded-lg border border-zinc-800 bg-zinc-900 p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Backend API checks</h2>
            <span className="font-mono text-sm text-zinc-400">
              {checks.length ? `${passing}/${checks.length} passing` : "—"}
            </span>
          </div>

          <ul className="mt-5 space-y-2">
            {checks.map((check) => (
              <li
                key={`${check.method} ${check.path}`}
                className="flex items-center gap-3 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm"
              >
                <span
                  className={`h-2.5 w-2.5 shrink-0 rounded-full ${
                    check.ok ? "bg-emerald-400" : "bg-rose-400"
                  }`}
                  aria-label={check.ok ? "passing" : "failing"}
                />
                <span className="min-w-0 flex-1 truncate font-mono text-zinc-100">
                  {check.method} {check.path}
                </span>
                <span className="font-mono text-zinc-400">
                  {check.status || check.error || "ERR"}
                </span>
                <span className="w-16 text-right font-mono text-zinc-500">
                  {check.ms}ms
                </span>
              </li>
            ))}
          </ul>

          <button
            type="button"
            onClick={loadChecks}
            disabled={isChecking}
            className="mt-6 inline-flex h-10 items-center rounded-md bg-cyan-400 px-4 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-cyan-200 focus:ring-offset-2 focus:ring-offset-zinc-900"
          >
            {isChecking ? "Running" : "Run checks"}
          </button>
        </section>
      </section>
    </main>
  );
}


export default App;
