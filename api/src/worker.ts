/** The Worker's fetch and scheduled handlers, over a store passed in. */
import { docsPage } from "./docs";
import { type Cache, kvCache } from "./cache";
import barsQuery from "./queries/bars.sql";
import latestQuery from "./queries/latest.sql";
import overviewQuery from "./queries/overview.sql";
import runsQuery from "./queries/runs.sql";
import signalsQuery from "./queries/signals.sql";
import slugsQuery from "./queries/slugs.sql";
import statsQuery from "./queries/stats.sql";
import {
  type Endpoint,
  type Failure,
  dataHeaders,
  errorBody,
  errorHeaders,
  isNotModified,
  notFound,
  preflightHeaders,
  route,
  storeUnavailable,
  tickerForSlug,
  versionOf,
} from "./route";
import { StoreUnavailableError } from "./error";
import type { Store, StoreEnv } from "./store";

export interface Env extends StoreEnv {
  CACHE: KVNamespace;
  ALLOWED_ORIGIN: string;
}

type CacheOutcome = "hit" | "miss" | "304" | "none";

const QUERIES: Record<Endpoint, string> = {
  latest: latestQuery,
  overview: overviewQuery,
  runs: runsQuery,
  signals: signalsQuery,
  stats: statsQuery,
};

interface Answer {
  response: Response;
  cache: CacheOutcome;
}

/** Everything one request shares: the cache, the store and where it was asked from. */
interface Context {
  cache: Cache;
  store: Store;
  origin: string | null;
  allowed: string;
}

const failure = (context: Context, problem: Failure, cache: CacheOutcome = "none"): Answer => ({
  response: new Response(errorBody(problem), {
    status: problem.status,
    headers: errorHeaders(problem, context.origin, context.allowed),
  }),
  cache,
});

/** The data version: from KV, else from the store's latest run, which is then cached. */
async function currentVersion(context: Context): Promise<{ version: string; queried: boolean }> {
  const known = await context.cache.version();
  if (known !== null) return { version: known, queried: false };
  const body = await context.store(latestQuery, []);
  const version = versionOf(body);
  await context.cache.put(version, "latest", body);
  await context.cache.setVersion(version);
  return { version, queried: true };
}

/** A body from KV under the version, else from the store and then cached. */
async function body(
  context: Context,
  version: string,
  name: string,
  query: string,
  params: string[],
): Promise<{ text: string; cache: CacheOutcome; stored: boolean }> {
  const cached = await context.cache.get(version, name);
  if (cached !== null) return { text: cached, cache: "hit", stored: true };
  const text = await context.store(query, params);
  const stored = await context.cache.put(version, name, text);
  return { text, cache: "miss", stored };
}

async function answer(request: Request, context: Context): Promise<Answer> {
  const url = new URL(request.url);
  const target = route(request.method, url.pathname);
  switch (target.kind) {
    case "error":
      return failure(context, target.failure);
    case "preflight":
      return {
        response: new Response(null, { status: 204, headers: preflightHeaders(context.origin, context.allowed) }),
        cache: "none",
      };
    case "docs":
      return {
        response: new Response(docsPage(url.origin), {
          headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "public, max-age=3600" },
        }),
        cache: "none",
      };
  }
  const { version, queried } = await currentVersion(context);
  if (isNotModified(request.headers.get("If-None-Match"), version)) {
    return {
      response: new Response(null, { status: 304, headers: dataHeaders(version, context.origin, context.allowed) }),
      cache: "304",
    };
  }
  let result: Awaited<ReturnType<typeof body>>;
  if (target.kind === "data") {
    result = await body(context, version, target.endpoint, QUERIES[target.endpoint], []);
  } else {
    const slugs = await body(context, version, "slugs", slugsQuery, []);
    const ticker = tickerForSlug(slugs.text, target.slug);
    if (ticker === null) return failure(context, notFound(`No instrument with slug '${target.slug}'`));
    result = await body(context, version, `bars/${target.slug}`, barsQuery, [ticker]);
  }
  const headers = dataHeaders(version, context.origin, context.allowed);
  if (!result.stored) headers["Cache-Control"] = "no-store";
  return { response: new Response(result.text, { headers }), cache: queried ? "miss" : result.cache };
}

/** Refill the cache under the store's current version when it has moved. */
export async function refresh(cache: Cache, store: Store): Promise<"moved" | "same"> {
  const latest = await store(latestQuery, []);
  const version = versionOf(latest);
  if ((await cache.version()) === version) return "same";
  await cache.put(version, "latest", latest);
  await cache.put(version, "overview", await store(overviewQuery, []));
  await cache.put(version, "runs", await store(runsQuery, []));
  await cache.put(version, "slugs", await store(slugsQuery, []));
  await cache.put(version, "signals", await store(signalsQuery, []));
  await cache.put(version, "stats", await store(statsQuery, []));
  await cache.setVersion(version);
  return "moved";
}

/** Build the Worker over the store it reads, so tests pass a fake. */
export function createWorker(makeStore: (env: Env) => Store) {
  return {
    async fetch(request: Request, env: Env): Promise<Response> {
      const started = Date.now();
      const context: Context = {
        cache: kvCache(env.CACHE),
        store: makeStore(env),
        origin: request.headers.get("Origin"),
        allowed: env.ALLOWED_ORIGIN,
      };
      let result: Answer;
      try {
        result = await answer(request, context);
      } catch (problem) {
        if (!(problem instanceof StoreUnavailableError)) throw problem;
        result = failure(context, storeUnavailable);
      }
      console.log(
        JSON.stringify({
          path: new URL(request.url).pathname,
          status: result.response.status,
          cache: result.cache,
          ms: Date.now() - started,
        }),
      );
      return result.response;
    },

    async scheduled(_controller: ScheduledController, env: Env): Promise<void> {
      try {
        const outcome = await refresh(kvCache(env.CACHE), makeStore(env));
        console.log(JSON.stringify({ cron: outcome }));
      } catch (problem) {
        if (!(problem instanceof StoreUnavailableError)) throw problem;
        console.log(JSON.stringify({ cron: "store_unavailable" }));
      }
    },
  };
}
