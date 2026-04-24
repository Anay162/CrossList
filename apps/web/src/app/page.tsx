import { MatchPanel } from "@/app/match-panel";

const steps = [
  {
    title: "Upload",
    description:
      "Bring in your unofficial transcript and let CrossList organize the courses that need transfer answers.",
  },
  {
    title: "Match",
    description:
      "Compare official ASSIST articulations alongside semantic matches that uncover likely equivalents beyond prior agreements.",
  },
  {
    title: "Appeal",
    description:
      "Open a registrar-ready packet with course descriptions, similarity evidence, and the context needed to make your case.",
  },
] as const;

const demoResults = [
  {
    source: "MATH 7",
    target: "MAT 021A",
    title: "Calculus",
    status: "Official Transfer",
    tone: "green",
    detail: "Confirmed by ASSIST 2025",
  },
  {
    source: "CS 55",
    target: "ECS 032A",
    title: "Introduction to Programming",
    status: "Official Transfer",
    tone: "green",
    detail: "Confirmed by ASSIST 2025",
  },
  {
    source: "ENGL 1D",
    target: "ENL 003",
    title: "Introduction to Literature",
    status: "84% Similar",
    tone: "yellow",
    detail: "Likely equivalent — both cover expository writing and critical analysis at the college level",
  },
] as const;

type StatsPayload = {
  institutions: number;
  courses: number;
  articulations: number;
};

async function getStats(): Promise<StatsPayload | null> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  try {
    const response = await fetch(`${apiUrl}/api/stats`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const data = (await response.json()) as StatsPayload;
    return data;
  } catch {
    return null;
  }
}

export default async function Home() {
  const stats = await getStats();
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  return (
    <main className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 sm:px-10">
          <a href="#" className="text-xl font-bold tracking-tight text-slate-900">
            CrossList
          </a>
          <a
            href="https://github.com/Anay162/CrossList"
            target="_blank"
            rel="noreferrer"
            aria-label="CrossList GitHub repository"
            className="rounded-md border border-slate-200 p-2 text-slate-700 transition hover:bg-slate-50"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden="true">
              <path d="M12 .5C5.649.5.5 5.649.5 12c0 5.084 3.292 9.399 7.862 10.92.575.106.785-.25.785-.556 0-.274-.01-1-.016-1.963-3.198.695-3.873-1.541-3.873-1.541-.523-1.328-1.278-1.681-1.278-1.681-1.044-.714.08-.7.08-.7 1.155.082 1.763 1.186 1.763 1.186 1.026 1.758 2.692 1.25 3.348.956.104-.743.401-1.25.729-1.537-2.553-.29-5.238-1.277-5.238-5.684 0-1.255.448-2.282 1.183-3.087-.119-.29-.513-1.458.112-3.04 0 0 .965-.309 3.162 1.18A10.96 10.96 0 0 1 12 6.05c.974.004 1.955.132 2.87.388 2.195-1.489 3.158-1.18 3.158-1.18.627 1.582.233 2.75.115 3.04.737.805 1.18 1.832 1.18 3.087 0 4.418-2.69 5.39-5.252 5.675.412.355.78 1.057.78 2.131 0 1.539-.014 2.78-.014 3.158 0 .309.207.668.79.555C20.21 21.395 23.5 17.082 23.5 12 23.5 5.649 18.351.5 12 .5Z" />
            </svg>
          </a>
        </div>
      </header>

      <section className="mx-auto w-full max-w-6xl px-6 py-20 text-center sm:px-10">
        <div className="inline-flex items-center rounded-full border border-sky-200 bg-white px-3 py-1 text-xs font-medium uppercase tracking-[0.24em] text-sky-700 shadow-sm">
          California transfer-credit discovery
        </div>
        <div className="mt-8 mx-auto max-w-3xl space-y-5">
          <h1 className="font-serif text-5xl tracking-tight text-slate-900 sm:text-7xl">
            CrossList
          </h1>
          <p className="text-lg leading-8 text-slate-600 sm:text-xl">
            Find the transfer credits other tools miss.
          </p>
          <p className="mx-auto max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">
            Transferology shows you what&apos;s been officially approved. CrossList also shows you
            what probably transfers and gives you the paperwork to prove it.
          </p>
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-6 sm:px-10">
          <div className="grid gap-3 lg:grid-cols-3">
            {demoResults.map((result) => (
              <article
                key={`${result.source}-${result.target}`}
                className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 space-y-2 text-left">
                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                      <span>{result.source}</span>
                      <span className="text-slate-400">→</span>
                      <span>{result.target}</span>
                    </div>
                    <p className="text-sm text-slate-700">{result.title}</p>
                    <p className="text-xs leading-5 text-slate-500">{result.detail}</p>
                  </div>
                  <span
                    className={
                      result.tone === "green"
                        ? "inline-flex shrink-0 rounded-full border border-green-300 bg-green-100 px-3 py-1 text-xs font-medium text-green-800"
                        : "inline-flex shrink-0 rounded-full border border-yellow-300 bg-yellow-100 px-3 py-1 text-xs font-medium text-yellow-800"
                    }
                  >
                    {result.status}
                  </span>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <MatchPanel apiUrl={apiUrl} />

      <section id="how" className="border-t border-slate-200 bg-white/70 py-24">
        <div className="mx-auto max-w-6xl px-6 sm:px-10">
          <div className="max-w-2xl">
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-sky-700">
              How it works
            </p>
            <h2 className="mt-4 font-serif text-3xl tracking-tight text-slate-900 sm:text-4xl">
              Start with what you&apos;ve already taken. Leave with a transfer case you can use.
            </h2>
          </div>
          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {steps.map((step, index) => (
              <article
                key={step.title}
                className="rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-[0_12px_40px_rgba(15,23,42,0.06)]"
              >
                <p className="text-sm font-medium text-sky-700">0{index + 1}</p>
                <h3 className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">
                  {step.title}
                </h3>
                <p className="mt-3 text-sm leading-7 text-slate-600">{step.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white py-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 text-sm text-slate-500 sm:px-10 md:flex-row md:items-center md:justify-between">
          <p>Built for California community college students navigating transfer credit uncertainty.</p>
          {stats ? (
            <p>
              {stats.courses} courses indexed across {stats.institutions} institutions.{" "}
              {stats.articulations} articulations loaded.
            </p>
          ) : null}
        </div>
      </footer>
    </main>
  );
}
