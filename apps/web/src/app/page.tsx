import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

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

  return (
    <main className="min-h-screen">
      <section className="mx-auto flex min-h-screen w-full max-w-6xl flex-col items-center justify-center px-6 py-24 text-center sm:px-10">
        <div className="inline-flex items-center rounded-full border border-sky-200 bg-white/75 px-3 py-1 text-xs font-medium uppercase tracking-[0.24em] text-sky-700 shadow-sm backdrop-blur">
          California transfer-credit discovery
        </div>
        <div className="mt-8 max-w-3xl space-y-6">
          <h1 className="font-serif text-5xl tracking-tight text-slate-900 sm:text-7xl">
            CrossList
          </h1>
          <p className="text-lg leading-8 text-slate-600 sm:text-xl">
            Find the transfer credits other tools miss.
          </p>
          <p className="mx-auto max-w-2xl text-sm leading-7 text-slate-600 sm:text-base">
            Official articulations when they exist, evidence-backed likely matches when they
            don&apos;t. Built for community college students trying to transfer with fewer lost
            credits.
          </p>
          {stats ? (
            <p className="mx-auto max-w-2xl text-sm leading-7 text-slate-500">
              {stats.courses} courses indexed across {stats.institutions} institutions.{" "}
              {stats.articulations} articulations loaded.
            </p>
          ) : null}
        </div>
        <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row">
          <div title="Coming in Phase 3">
            <Button
              disabled
              size="lg"
              className="min-w-48 rounded-full px-6 shadow-sm"
            >
              Check my transcript
            </Button>
          </div>
          <Link
            href="#how"
            className={cn(buttonVariants({ variant: "outline", size: "lg" }), "min-w-40 rounded-full px-6")}
          >
            How it works
          </Link>
        </div>
      </section>

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
    </main>
  );
}
