import { useEffect, useState } from "react";

import { createItem, getApiBaseUrl, getHealth, getItems } from "./api";


function App() {
  const [health, setHealth] = useState("checking");
  const [items, setItems] = useState([]);
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function loadData() {
    setError("");
    try {
      const [healthResponse, itemResponse] = await Promise.all([
        getHealth(),
        getItems(),
      ]);
      setHealth(healthResponse.status);
      setItems(itemResponse);
    } catch (requestError) {
      setHealth("offline");
      setError(requestError.message);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle) {
      setError("Enter an item title before adding it.");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      const createdItem = await createItem(nextTitle);
      setItems((currentItems) => [...currentItems, createdItem]);
      setTitle("");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsSaving(false);
    }
  }

  const isOnline = health === "ok";

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

        <div className="grid gap-4 md:grid-cols-[1fr_1.3fr]">
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
            <button
              type="button"
              onClick={loadData}
              className="mt-6 inline-flex h-10 items-center rounded-md bg-cyan-400 px-4 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300 focus:outline-none focus:ring-2 focus:ring-cyan-200 focus:ring-offset-2 focus:ring-offset-zinc-900"
            >
              Refresh API
            </button>
          </section>

          <section className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
            <h2 className="text-lg font-semibold">Sample SQLite items</h2>
            <form onSubmit={handleSubmit} className="mt-4 flex gap-3">
              <label className="sr-only" htmlFor="item-title">
                Item title
              </label>
              <input
                id="item-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Add a starter task"
                className="min-w-0 flex-1 rounded-md border border-zinc-700 bg-zinc-950 px-3 text-sm text-zinc-50 outline-none transition placeholder:text-zinc-500 focus:border-cyan-300"
              />
              <button
                type="submit"
                disabled={isSaving}
                className="h-10 rounded-md bg-emerald-400 px-4 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSaving ? "Adding" : "Add"}
              </button>
            </form>

            {error ? (
              <p className="mt-4 rounded-md border border-rose-400/40 bg-rose-400/10 px-3 py-2 text-sm text-rose-100">
                {error}
              </p>
            ) : null}

            <ul className="mt-5 space-y-3">
              {items.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center gap-3 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-3 text-sm"
                >
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-zinc-800 font-mono text-xs text-cyan-200">
                    {item.id}
                  </span>
                  <span>{item.title}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </section>
    </main>
  );
}


export default App;
