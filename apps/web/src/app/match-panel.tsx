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

type CourseSuggestion = {
  course_id: string;
  course_code: string;
  title: string;
};

type CourseLookupError = {
  course_code: string;
  error: string;
  institution: string;
};

type MatchResponseItem = {
  input_course_code: string;
  resolved_course_code: string | null;
  match_result: MatchResult | null;
  suggestions: CourseSuggestion[] | null;
  error: CourseLookupError | null;
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

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
      <path d="M12 2 4 5v6c0 5.25 3.438 9.563 8 11 4.563-1.438 8-5.75 8-11V5l-8-3Zm0 2.125 6 2.25v4.625c0 4.13-2.54 7.612-6 8.94-3.46-1.328-6-4.81-6-8.94V6.375l6-2.25Z" />
    </svg>
  );
}

function SparklesIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
      <path d="m12 2 1.7 4.8L18.5 8l-4.8 1.2L12 14l-1.7-4.8L5.5 8l4.8-1.2L12 2Zm7 10 .9 2.6L22.5 15l-2.6.6L19 18.2l-.9-2.6-2.6-.6 2.6-.4.9-2.6ZM6 13l1.2 3.3 3.3 1.2-3.3 1.2L6 22l-1.2-3.3L1.5 17.5l3.3-1.2L6 13Z" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current" aria-hidden="true">
      <path d="M11 3h2v9.17l2.59-2.58L17 11l-5 5-5-5 1.41-1.41L11 12.17V3Zm-7 14h16v4H4v-4Z" />
    </svg>
  );
}

function formatSourceCourse(course: CourseSchema) {
  return `${course.subject_code} ${course.code}`;
}

function formatTargetCourse(course: CourseSchema) {
  return `${course.subject_code} ${course.code}`;
}

function primaryMatch(result: MatchResult): CourseMatch | null {
  return result.matches[0] ?? null;
}

function parseCourseLines(value: string) {
  return value
    .split(/[\n,]+/)
    .map((line) => line.trim())
    .filter(Boolean);
}

export function MatchPanel({ apiUrl }: MatchPanelProps) {
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [sourceInstitution, setSourceInstitution] = useState("SMC");
  const [targetInstitution, setTargetInstitution] = useState("UC Davis");
  const [coursesText, setCoursesText] = useState("MATH 7\nCS 55\nENGL 1\nPSYCH 1");
  const [results, setResults] = useState<MatchResponseItem[]>([]);
  const [selectedResult, setSelectedResult] = useState<{
    sourceCourse: CourseSchema;
    match: CourseMatch;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [networkError, setNetworkError] = useState<string | null>(null);
  const [isLoadingInstitutions, setIsLoadingInstitutions] = useState(true);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [isDownloadingReport, setIsDownloadingReport] = useState(false);
  const [descriptionInputs, setDescriptionInputs] = useState<Record<string, string>>({});
  const [descriptionResults, setDescriptionResults] = useState<Record<string, CourseMatch[]>>({});
  const [descriptionErrors, setDescriptionErrors] = useState<Record<string, string>>({});
  const [descriptionLoading, setDescriptionLoading] = useState<Record<string, boolean>>({});

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

  async function runMatchRequest(rawCoursesText: string) {
    setError(null);
    setNetworkError(null);
    setIsLoadingResults(true);
    setDescriptionResults({});
    setDescriptionErrors({});

    const sourceCourses = parseCourseLines(rawCoursesText).map((courseCode) => ({
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

      const data = (await response.json()) as MatchResponseItem[];
      setResults(data);
    } catch (submitError) {
      setResults([]);
      if (submitError instanceof TypeError) {
        setNetworkError("Could not reach the CrossList server. Is the API running?");
      } else {
        setError(submitError instanceof Error ? submitError.message : "Unable to find matches");
      }
    } finally {
      setIsLoadingResults(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isLoadingResults) {
      return;
    }

    await runMatchRequest(coursesText);
  }

  async function handleSuggestionSelect(inputCourseCode: string, selectedCourseCode: string) {
    const updatedLines = parseCourseLines(coursesText).map((line) =>
      line === inputCourseCode ? selectedCourseCode : line
    );
    const updatedText = updatedLines.join("\n");
    setCoursesText(updatedText);
    await runMatchRequest(updatedText);
  }

  async function handleDescriptionSearch(result: MatchResult) {
    const key = result.source_course_id;
    const description = (descriptionInputs[key] ?? "").trim();
    if (!description) {
      setDescriptionErrors((current) => ({
        ...current,
        [key]: "Add a short description before searching.",
      }));
      return;
    }

    setDescriptionLoading((current) => ({ ...current, [key]: true }));
    setDescriptionErrors((current) => ({ ...current, [key]: "" }));

    try {
      const response = await fetch(`${apiUrl}/api/match/by-description`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          description,
          target_institution_short_name: targetInstitution,
          similarity_threshold: UI_SIMILARITY_THRESHOLD,
        }),
      });

      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        throw new Error(payload.detail ?? "Unable to search by description");
      }

      const matches = (await response.json()) as CourseMatch[];
      setDescriptionResults((current) => ({ ...current, [key]: matches }));
      if (matches.length === 0) {
        setDescriptionErrors((current) => ({
          ...current,
          [key]: `No close description matches found at ${targetInstitution}.`,
        }));
      }
    } catch (searchError) {
      if (searchError instanceof TypeError) {
        setNetworkError("Could not reach the CrossList server. Is the API running?");
      } else {
        setDescriptionErrors((current) => ({
          ...current,
          [key]: searchError instanceof Error ? searchError.message : "Unable to search by description",
        }));
      }
    } finally {
      setDescriptionLoading((current) => ({ ...current, [key]: false }));
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

            <Button
              type="submit"
              size="lg"
              className="w-full rounded-lg sm:w-auto"
              disabled={isLoadingInstitutions || isLoadingResults}
            >
              {isLoadingResults ? (
                <>
                  <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  Finding Matches...
                </>
              ) : (
                "Find Matches"
              )}
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

          {networkError ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {networkError}
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
                if (result.error) {
                  return (
                    <Card key={`error-${result.input_course_code}`} className="space-y-3">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="space-y-1">
                          <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
                            {result.input_course_code}
                          </p>
                          <h3 className="text-lg font-semibold text-slate-900">Course not found</h3>
                        </div>
                        <span
                          className={cn(
                            "inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-medium",
                            BADGE_STYLES.NONE
                          )}
                        >
                          {BADGE_LABELS.NONE}
                        </span>
                      </div>
                      <p className="text-sm text-slate-600">
                        {result.error.course_code} was not found at {result.error.institution}.
                      </p>
                    </Card>
                  );
                }

                if (result.suggestions && result.suggestions.length > 0) {
                  return (
                    <Card key={`suggestions-${result.input_course_code}`} className="space-y-3">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="space-y-1">
                          <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
                            {result.input_course_code}
                          </p>
                          <h3 className="text-lg font-semibold text-slate-900">Choose the course you meant</h3>
                        </div>
                        <span className="inline-flex w-fit items-center rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                          Suggestions
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {result.suggestions.map((suggestion) => (
                          <button
                            key={suggestion.course_id}
                            type="button"
                            onClick={() => void handleSuggestionSelect(result.input_course_code, suggestion.course_code)}
                            className="rounded-full border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 transition hover:border-sky-300 hover:bg-sky-50"
                          >
                            {suggestion.course_code} — {suggestion.title}
                          </button>
                        ))}
                      </div>
                    </Card>
                  );
                }

                const matchResult = result.match_result;
                if (!matchResult) {
                  return null;
                }

                const match = primaryMatch(matchResult);
                if (!match) {
                  return null;
                }

                return (
                  <Card
                    key={matchResult.source_course_id}
                    className={cn(
                      "space-y-3 hover:shadow-md transition-shadow duration-150",
                      match.match_type === "SEMANTIC" && "cursor-pointer focus-within:ring-2 focus-within:ring-yellow-300 hover:border-yellow-300"
                    )}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1 space-y-3">
                        <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
                          <div className="min-w-0">
                            <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
                              Source
                            </p>
                            <p className="truncate text-base font-semibold text-slate-900">
                              {result.resolved_course_code ?? formatSourceCourse(matchResult.source_course)} —{" "}
                              {matchResult.source_course.title}
                            </p>
                          </div>
                          <span className="text-lg text-slate-400">→</span>
                          <div className="min-w-0">
                            <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
                              Best Match
                            </p>
                            <p className="truncate text-base font-semibold text-slate-900">
                              {match.match_type === "NONE"
                                ? `No equivalent found at ${targetInstitution}`
                                : `${formatTargetCourse(match.target_course)} — ${match.target_course.title}`}
                            </p>
                          </div>
                        </div>
                      </div>
                      <span
                        className={cn(
                          "inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
                          BADGE_STYLES[match.match_type]
                        )}
                      >
                        {match.match_type === "OFFICIAL" ? <ShieldIcon /> : null}
                        {match.match_type === "SEMANTIC" ? <SparklesIcon /> : null}
                        {BADGE_LABELS[match.match_type]}
                      </span>
                    </div>

                    <div
                      className="space-y-2 text-sm text-slate-700"
                      role={match.match_type === "SEMANTIC" ? "button" : undefined}
                      tabIndex={match.match_type === "SEMANTIC" ? 0 : -1}
                      onClick={() => {
                        if (match.match_type === "SEMANTIC") {
                          setSelectedResult({ sourceCourse: matchResult.source_course, match });
                        }
                      }}
                      onKeyDown={(event) => {
                        if (match.match_type === "SEMANTIC" && (event.key === "Enter" || event.key === " ")) {
                          event.preventDefault();
                          setSelectedResult({ sourceCourse: matchResult.source_course, match });
                        }
                      }}
                    >
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
                          <div className="h-1 rounded bg-slate-200">
                            <div
                              className="h-1 rounded bg-yellow-400"
                              style={{ width: `${Math.round(match.similarity_score * 100)}%` }}
                            />
                          </div>
                          <p className="text-sm leading-6 text-slate-700">{match.explanation}</p>
                        </>
                      ) : null}

                      {match.match_type === "NONE" ? (
                        <div className="space-y-3">
                          <p className="text-sm text-slate-600">No equivalent found at {targetInstitution}</p>
                          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                            <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500">
                              Tip: Try searching by course description instead
                            </p>
                            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                              <input
                                type="text"
                                value={descriptionInputs[matchResult.source_course_id] ?? ""}
                                onChange={(event) =>
                                  setDescriptionInputs((current) => ({
                                    ...current,
                                    [matchResult.source_course_id]: event.target.value,
                                  }))
                                }
                                placeholder="e.g. introduction to programming in Python"
                                className="h-10 flex-1 rounded-lg border border-gray-300 bg-white px-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-200"
                              />
                              <Button
                                type="button"
                                variant="outline"
                                onClick={() => void handleDescriptionSearch(matchResult)}
                                disabled={descriptionLoading[matchResult.source_course_id]}
                              >
                                {descriptionLoading[matchResult.source_course_id] ? "Searching..." : "Search by Description"}
                              </Button>
                            </div>
                            {descriptionErrors[matchResult.source_course_id] ? (
                              <p className="mt-2 text-sm text-red-700">{descriptionErrors[matchResult.source_course_id]}</p>
                            ) : null}
                            {descriptionResults[matchResult.source_course_id]?.length ? (
                              <div className="mt-3 space-y-2">
                                {descriptionResults[matchResult.source_course_id].map((candidate) => (
                                  <div
                                    key={candidate.target_course_id}
                                    className="rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-slate-700"
                                  >
                                    <p className="font-medium text-slate-900">
                                      {formatTargetCourse(candidate.target_course)} {candidate.target_course.title}
                                    </p>
                                    <p>{Math.round(candidate.similarity_score * 100)}% similar</p>
                                  </div>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        </div>
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

            <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_1px_minmax(0,1fr)]">
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

              <div className="hidden bg-slate-200 lg:block" />

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
                  <div className="flex items-center justify-between text-sm text-slate-700">
                    <p className="font-medium">Similarity Score</p>
                    <p>{Math.round(selectedResult.match.similarity_score * 100)}%</p>
                  </div>
                  <div className="h-3 rounded-full bg-slate-200">
                    <div
                      className="h-3 rounded-full bg-yellow-400"
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

              <div className="bg-blue-50 rounded-lg p-4">
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
                <DownloadIcon />
                <span>{isDownloadingReport ? "Generating Report..." : "Download Comparison Report (PDF)"}</span>
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
