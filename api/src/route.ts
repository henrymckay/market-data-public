/** The pure core: a request in, a decision out. No I/O lives here. */

export type Endpoint = "latest" | "overview" | "runs";

export type Route =
  | { kind: "data"; endpoint: Endpoint }
  | { kind: "bars"; slug: string }
  | { kind: "docs" }
  | { kind: "preflight" }
  | { kind: "error"; failure: Failure };

export type ErrorCode = "not_found" | "method_not_allowed" | "store_unavailable";

export interface Failure {
  status: 404 | 405 | 503;
  code: ErrorCode;
  error: string;
}

const DATA_PATHS: Record<string, Endpoint> = {
  "/api/latest": "latest",
  "/api/overview": "overview",
  "/api/runs": "runs",
};

const BARS_PREFIX = "/api/bars/";
const SLUG = /^[a-z0-9]+$/;

export const notFound = (what: string): Failure => ({
  status: 404,
  code: "not_found",
  error: `${what}; see /api/overview for the list.`,
});

export const storeUnavailable: Failure = {
  status: 503,
  code: "store_unavailable",
  error: "MotherDuck did not answer; try again in a minute.",
};

/** Decide what a method and path ask for. Every parameter but the path is ignored. */
export function route(method: string, pathname: string): Route {
  if (method === "OPTIONS") return { kind: "preflight" };
  if (method !== "GET" && method !== "HEAD") {
    return {
      kind: "error",
      failure: {
        status: 405,
        code: "method_not_allowed",
        error: "Only GET, HEAD and OPTIONS are allowed.",
      },
    };
  }
  if (pathname === "/") return { kind: "docs" };
  const endpoint = DATA_PATHS[pathname];
  if (endpoint) return { kind: "data", endpoint };
  if (pathname.startsWith(BARS_PREFIX)) {
    const slug = pathname.slice(BARS_PREFIX.length);
    if (SLUG.test(slug)) return { kind: "bars", slug };
    return { kind: "error", failure: notFound(`No instrument with slug '${slug}'`) };
  }
  return { kind: "error", failure: notFound(`No such path '${pathname}'`) };
}

/** The ticker a slug names in the overview body, or null when none does. */
export function tickerForSlug(overviewBody: string, slug: string): string | null {
  const rows: unknown = JSON.parse(overviewBody);
  if (!Array.isArray(rows)) return null;
  for (const row of rows as { slug?: unknown; ticker?: unknown }[]) {
    if (row.slug === slug && typeof row.ticker === "string") return row.ticker;
  }
  return null;
}

/** The data version a `latest` body names: its `ended`, or `none` before any run. */
export function versionOf(latestBody: string): string {
  const latest: unknown = JSON.parse(latestBody);
  if (latest !== null && typeof latest === "object" && "ended" in latest) {
    const { ended } = latest as { ended: unknown };
    if (typeof ended === "string") return ended;
  }
  return "none";
}

export const etagFor = (version: string): string => `"${version}"`;

/** Whether an `If-None-Match` header names the current version. */
export function isNotModified(ifNoneMatch: string | null, version: string): boolean {
  if (ifNoneMatch === null) return false;
  const wanted = etagFor(version);
  return ifNoneMatch.split(",").some((tag) => tag.trim() === wanted || tag.trim() === `W/${wanted}`);
}

const CORS_METHODS = "GET, HEAD, OPTIONS";

/** Headers every response carries: CORS for the one allowed browser origin. */
export function corsHeaders(origin: string | null, allowed: string): Record<string, string> {
  const headers: Record<string, string> = { Vary: "Origin" };
  if (origin !== null && origin === allowed) headers["Access-Control-Allow-Origin"] = origin;
  return headers;
}

export function preflightHeaders(origin: string | null, allowed: string): Record<string, string> {
  return {
    ...corsHeaders(origin, allowed),
    Allow: CORS_METHODS,
    "Access-Control-Allow-Methods": CORS_METHODS,
    "Access-Control-Allow-Headers": "If-None-Match",
    "Access-Control-Max-Age": "86400",
  };
}

export function dataHeaders(version: string, origin: string | null, allowed: string): Record<string, string> {
  return {
    ...corsHeaders(origin, allowed),
    "Content-Type": "application/json",
    "Cache-Control": "public, max-age=60",
    ETag: etagFor(version),
  };
}

export function errorHeaders(failure: Failure, origin: string | null, allowed: string): Record<string, string> {
  return {
    ...corsHeaders(origin, allowed),
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
    ...(failure.status === 503 ? { "Retry-After": "60" } : {}),
    ...(failure.status === 405 ? { Allow: CORS_METHODS } : {}),
  };
}

export const errorBody = (failure: Failure): string =>
  JSON.stringify({ error: failure.error, code: failure.code });
