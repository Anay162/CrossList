"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Institution = {
  id: string;
  name: string;
  short_name: string;
  kind: "CC" | "UC" | "CSU" | "OTHER";
};

type MatchType = "OFFICIAL" | "SEMANTIC" | "NONE";

type CourseSchema = {
  id: string;
  institution_id: string;
  institution_short_name: string;
  institution_name: string;
  subject_code: string;
  code: string;
  title: string;
  description: string;
  units: number | null;
};

type CourseMatch = {
  target_course_id: string;
  target_course: CourseSchema;
  similarity_score: number;
  match_type: MatchType;
  articulation_id: string | null;
  agreement_year?: number | null;
  explanation: string | null;
};

type MatchResult = {
  source_course_id: string;
  source_course: CourseSchema;
  matches: CourseMatch[];
};

type MatchPanelProps = {
  apiUrl: string;
};

const UI_SIMILARITY_THRESHOLD = 0.6;

const BADGE_STYLES: Record<MatchType, string> = {
  OFFICIAL: "bg-green-100 text-green-800 border border-green-300",
  SEMANTIC: "bg-yellow-100 text-yellow-800 border border-yellow-300",
  NONE: "bg-red-100 text-red-800 border border-red-300",
};

const BADGE_LABELS: Record<MatchType, string> = {
  OFFICIAL: "Official Transfer",
  SEMANTIC: "Likely Equivalent",
  NONE: "No Match Found",
};

function formatSourceCourse(course: CourseSchema) {
  return `${course.subject_code} ${course.code}`;
}

function formatTargetCourse(course: CourseSchema) {
  return `${course.subject_code} ${course.code}`;
}

function primaryMatch(result: MatchResult): CourseMatch | null {
  return result.matches[0] ?? null;
}

export function MatchPanel({ apiUrl }: MatchPanelProps) {
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [sourceInstitution, setSourceInstitution] = useState("SMC");
  const [targetInstitution, setTargetInstitution] = useState("UC Davis");
  const [coursesText, setCoursesText] = useState("MATH 7\nCS 55\nENGL 1\nPSYCH 1");
  const [results, setResults] = useState<MatchResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<{
    sourceCourse: CourseSchema;
    match: CourseMatch;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingInstitutions, setIsLoadingInstitutions] = useState(true);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [isDownloadingReport, setIsDownloadingReport] = useState(false);

  useEffect(() => {
    async function loadInstitutions() {
      try {
        const response = await fetch(`${apiUrl}/api/institutions`, { cache: "no-store" });
        if (!response.ok) {
          throw new Error("Unable to load institutions");
        }
        const data = (await response.json()) as Institution[];
        setInstitutions(data);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Unable to load institutions");
      } finally {
        setIsLoadingInstitutions(false);
      }
    }

    void loadInstitutions();
  }, [apiUrl]);

  const sourceOptions = useMemo(
    () => institutions.filter((institution) => institution.kind === "CC"),
    [institutions]
  );
  const targetOptions = useMemo(
    () => institutions.filter((institution) => institution.kind !== "CC"),
    [institutions]
  );

  useEffect(() => {
    if (sourceOptions.length > 0 && !sourceOptions.some((option) => option.short_name === sourceInstitution)) {
      setSourceInstitution(sourceOptions[0].short_name);
    }
  }, [sourceInstitution, sourceOptions]);

  useEffect(() => {
    if (targetOptions.length > 0 && !targetOptions.some((option) => option.short_name === targetInstitution)) {
      setTargetInstitution(targetOptions[0].short_name);
    }
  }, [targetInstitution, targetOptions]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsLoadingResults(true);

    const sourceCourses = coursesText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((courseCode) => ({
        institution_short_name: sourceInstitution,
        course_code: courseCode,
      }));

    try {
      const response = await fetch(`${apiUrl}/api/match`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source_courses: sourceCourses,
          target_institution_short_name: targetInstitution,
          similarity_threshold: UI_SIMILARITY_THRESHOLD,
        }),
      });

      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        throw new Error(payload.detail ?? "Unable to find matches");
      }

      const data = (await response.json()) as MatchResult[];
      setResults(data);
    } catch (submitError) {
      setResults([]);
      setError(submitError instanceof Error ? submitError.message : "Unable to find matches");
    } finally {
      setIsLoadingResults(false);
    }
  }

  async function handleDownloadReport() {
    if (!selectedResult) {
      return;
    }

    setIsDownloadingReport(true);
    try {
      const response = await fetch(`${apiUrl}/api/match/report`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source_course_id: selectedResult.sourceCourse.id,
          target_course_id: selectedResult.match.target_course_id,
        }),
      });

      if (!response.ok) {
        throw new Error("Unable to generate comparison report");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `crosslist_${formatSourceCourse(selectedResult.sourceCourse).replace(/\s+/g, "_")}_${formatTargetCourse(selectedResult.match.target_course).replace(/\s+/g, "_")}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "Unable to generate comparison report");
    } finally {
      setIsDownloadingReport(false);
    }
  }

  return (
    <section className="border-t border-slate-200 bg-white/70 py-16">
      <div className="mx-auto grid max-w-6xl gap-6 px-6 sm:px-10 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <Card className="space-y-5">
          <div className="space-y-2">
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-sky-700">Course Input</p>
            <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Build your transfer list</h2>
            <p className="text-sm leading-6 text-slate-600">
              Paste the courses you&apos;ve already taken, choose a source college and target university,
              then let CrossList surface official and likely matches.
            </p>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <label htmlFor="courses" className="text-sm font-medium text-slate-900">
                Paste your courses
              </label>
              <textarea
                id="courses"
                value={coursesText}
                onChange={(event) => setCoursesText(event.target.value)}
                placeholder={"One course per line, e.g.:\nMATH 7\nCS 55\nENGL 1\nPSYCH 1"}
                className="min-h-48 w-full rounded-lg border border-gray-300 bg-white px-3 py-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-200"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="sourceInstitution" className="text-sm font-medium text-slate-900">
                  Source Institution
                </label>
                <select
                  id="sourceInstitution"
                  value={sourceInstitution}
                  onChange={(event) => setSourceInstitution(event.target.value)}
                  disabled={isLoadingInstitutions}
                  className="h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-200"
                >
                  {sourceOptions.map((institution) => (
                    <option key={institution.id} value={institution.short_name}>
                      {institution.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label htmlFor="targetInstitution" className="text-sm font-medium text-slate-900">
                  Target Institution
                </label>
                <select
                  id="targetInstitution"
                  value={targetInstitution}
                  onChange={(event) => setTargetInstitution(event.target.value)}
                  disabled={isLoadingInstitutions}
                  className="h-11 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-200"
                >
                  {targetOptions.map((institution) => (
                    <option key={institution.id} value={institution.short_name}>
                      {institution.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <Button type="submit" size="lg" className="w-full rounded-lg sm:w-auto" disabled={isLoadingInstitutions || isLoadingResults}>
              {isLoadingResults ? "Finding Matches..." : "Find Matches"}
            </Button>
          </form>
        </Card>

        <Card className="space-y-5">
          <div className="space-y-2">
            <p className="text-sm font-medium uppercase tracking-[0.18em] text-sky-700">Results</p>
            <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Transfer outcomes</h2>
            <p className="text-sm leading-6 text-slate-600">
              CrossList ranks official ASSIST agreements first, then likely semantic matches that are worth reviewing.
            </p>
          </div>

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              {error}
            </div>
          ) : null}

          {isLoadingResults ? (
            <div className="space-y-3" aria-live="polite" aria-busy="true">
              {[0, 1, 2].map((index) => (
                <div key={index} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="h-4 w-32 animate-pulse rounded bg-slate-200" />
                  <div className="mt-3 h-6 w-48 animate-pulse rounded bg-slate-200" />
                  <div className="mt-4 h-4 w-full animate-pulse rounded bg-slate-100" />
                  <div className="mt-2 h-4 w-5/6 animate-pulse rounded bg-slate-100" />
                </div>
              ))}
            </div>
          ) : results.length > 0 ? (
            <div className="space-y-3">
              {results.map((result) => {
                const match = primaryMatch(result);
                if (!match) {
                  return null;
                }

                return (
                  <Card
                    key={result.source_course_id}
                    className={cn(
                      "space-y-3",
                      match.match_type === "SEMANTIC" && "cursor-pointer focus-within:ring-2 focus-within:ring-yellow-300 hover:border-yellow-300"
                    )}
                  >
                    <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div className="space-y-1">
                        <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
                          {formatSourceCourse(result.source_course)}
                        </p>
                        <h3 className="text-lg font-semibold text-slate-900">{result.source_course.title}</h3>
                      </div>
                      <span
                        className={cn(
                          "inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-medium",
                          BADGE_STYLES[match.match_type]
                        )}
                      >
                        {BADGE_LABELS[match.match_type]}
                      </span>
                    </div>

                    <div
                      className="space-y-2 text-sm text-slate-700"
                      role={match.match_type === "SEMANTIC" ? "button" : undefined}
                      tabIndex={match.match_type === "SEMANTIC" ? 0 : -1}
                      onClick={() => {
                        if (match.match_type === "SEMANTIC") {
                          setSelectedResult({ sourceCourse: result.source_course, match });
                        }
                      }}
                      onKeyDown={(event) => {
                        if (match.match_type === "SEMANTIC" && (event.key === "Enter" || event.key === " ")) {
                          event.preventDefault();
                          setSelectedResult({ sourceCourse: result.source_course, match });
                        }
                      }}
                    >
                      <p className="font-medium text-slate-900">
                        Best match: {formatTargetCourse(match.target_course)} {match.target_course.title}
                      </p>

                      {match.match_type === "OFFICIAL" ? (
                        <p className="text-sm text-slate-600">
                          Confirmed by ASSIST.org {match.agreement_year ?? ""}
                        </p>
                      ) : null}

                      {match.match_type === "SEMANTIC" ? (
                        <>
                          <p className="text-sm text-slate-600">
                            {Math.round(match.similarity_score * 100)}% similar
                          </p>
                          <p className="text-sm leading-6 text-slate-700">{match.explanation}</p>
                        </>
                      ) : null}

                      {match.match_type === "NONE" ? (
                        <p className="text-sm text-slate-600">
                          No equivalent found — consider petitioning your registrar
                        </p>
                      ) : null}
                    </div>
                  </Card>
                );
              })}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-slate-300 px-4 py-10 text-sm leading-6 text-slate-500">
              Paste your courses and run a match to see official and likely transfer outcomes here.
            </div>
          )}
        </Card>
      </div>

      {selectedResult ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/55 px-4 py-8">
          <div className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-xl bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.18em] text-yellow-700">Likely Equivalent</p>
                <h3 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                  Course Comparison
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedResult(null)}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                Close
              </button>
            </div>

            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <div className="space-y-3 rounded-lg border border-gray-200 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">Source Course</p>
                <h4 className="text-lg font-semibold text-slate-900">
                  {selectedResult.sourceCourse.institution_name}
                </h4>
                <p className="text-sm font-medium text-slate-900">
                  {formatSourceCourse(selectedResult.sourceCourse)} — {selectedResult.sourceCourse.title}
                </p>
                <p className="text-sm text-slate-600">
                  Units: {selectedResult.sourceCourse.units ?? "N/A"}
                </p>
                <p className="text-sm leading-6 text-slate-700">{selectedResult.sourceCourse.description}</p>
              </div>

              <div className="space-y-3 rounded-lg border border-gray-200 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">Target Course</p>
                <h4 className="text-lg font-semibold text-slate-900">
                  {selectedResult.match.target_course.institution_name}
                </h4>
                <p className="text-sm font-medium text-slate-900">
                  {formatTargetCourse(selectedResult.match.target_course)} — {selectedResult.match.target_course.title}
                </p>
                <p className="text-sm text-slate-600">
                  Units: {selectedResult.match.target_course.units ?? "N/A"}
                </p>
                <div className="space-y-2">
                  <p className="text-sm text-slate-700">
                    Similarity score: {Math.round(selectedResult.match.similarity_score * 100)}%
                  </p>
                  <div className="h-2 rounded-full bg-slate-200">
                    <div
                      className="h-2 rounded-full bg-yellow-500"
                      style={{ width: `${Math.round(selectedResult.match.similarity_score * 100)}%` }}
                    />
                  </div>
                </div>
                <p className="text-sm leading-6 text-slate-700">{selectedResult.match.target_course.description}</p>
              </div>
            </div>

            <div className="mt-6 space-y-4">
              <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
                <p className="text-sm font-medium text-slate-900">AI explanation</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  {selectedResult.match.explanation}
                </p>
              </div>

              <div className="rounded-lg border border-gray-200 p-4">
                <p className="text-sm font-semibold text-slate-900">Next Steps</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  This match was identified by AI similarity analysis, not by a faculty committee. To request formal credit evaluation:
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-700">
                  1. Download the comparison report below
                  <br />
                  2. Bring it to {selectedResult.match.target_course.institution_name} Admissions or your academic advisor
                  <br />
                  3. Ask them to initiate a course substitution petition
                </p>
              </div>

              <Button
                type="button"
                size="lg"
                className="rounded-lg"
                onClick={() => void handleDownloadReport()}
                disabled={isDownloadingReport}
              >
                {isDownloadingReport ? "Generating Report..." : "Download Comparison Report (PDF)"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
