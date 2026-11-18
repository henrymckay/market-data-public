import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";
import { type Env, createWorker, refresh } from "../src/worker";
import { kvCache } from "../src/cache";
import { StoreUnavailableError } from "../src/error";

const LATEST = '{"day":"2026-11-17","ended":"2026-11-18T02:19:41Z","outcome":"stored","rows":9}';
const OVERVIEW = '[{"ticker":"^GSPC","slug":"gspc"},{"ticker":"AAPL","slug":"aapl"},{"ticker":"BTC-USD","slug":"btc-usd"}]';
const BARS = '{"ticker":"^GSPC","day":["2026-11-16"]}';
const ORIGIN = "https://henrymckay.github.io";

/** A fake store that answers by query text and counts what it was asked. */
function fakeStore(overrides: Partial<Record<string, string>> = {}) {
  const calls: { name: string; params: string[] }[] = [];
  const bodies: Record<string, string> = { latest: LATEST, overview: OVERVIEW, runs: "[]", bars: BARS, ...overrides };
  const store = async (query: string, params: string[]): Promise<string> => {
    const name = query.includes("from bars") ? "bars" : query.includes("from overview") ? "overview" : query.includes("from newest") ? "runs" : "latest";
    calls.push({ name, params });
    const body = bodies[name];
    if (body === undefined) throw new StoreUnavailableError();
    return body;
  };
  return { store, calls };
}

const testEnv = (): Env => env as unknown as Env;
const get = (path: string, init: RequestInit = {}) => new Request(`https://api.test${path}`, init);

async function clear() {
  const { keys } = await testEnv().CACHE.list();
  await Promise.all(keys.map((key) => testEnv().CACHE.delete(key.name)));
}

beforeEach(clear);

describe("data endpoints", () => {
  it("serves a body with its version as ETag and a minute of caching", async () => {
    const { store } = fakeStore();
    const response = await createWorker(() => store).fetch(get("/api/overview"), testEnv());

    expect(response.status).toBe(200);
    expect(await response.text()).toBe(OVERVIEW);
    expect(response.headers.get("ETag")).toBe('"2026-11-18T02:19:41Z"');
    expect(response.headers.get("Cache-Control")).toBe("public, max-age=60");
    expect(response.headers.get("Content-Type")).toBe("application/json");
  });

  it("queries the store once per key per data version", async () => {
    const { store, calls } = fakeStore();
    const worker = createWorker(() => store);

    await worker.fetch(get("/api/overview"), testEnv());
    const afterFirst = calls.length;
    await worker.fetch(get("/api/overview"), testEnv());
    await worker.fetch(get("/api/overview?v=anything&x=1"), testEnv());

    expect(calls.filter((call) => call.name === "overview")).toHaveLength(1);
    expect(calls.length).toBe(afterFirst);
  });

  it("returns a bars history for a known slug, asking for its ticker once", async () => {
    const { store, calls } = fakeStore();
    const worker = createWorker(() => store);

    const first = await worker.fetch(get("/api/bars/gspc"), testEnv());
    await worker.fetch(get("/api/bars/gspc"), testEnv());

    expect(await first.text()).toBe(BARS);
    expect(calls.filter((call) => call.name === "bars")).toEqual([{ name: "bars", params: ["^GSPC"] }]);
  });

  it("serves an instrument whose slug keeps a hyphen, as BTC-USD's does", async () => {
    const { store, calls } = fakeStore();

    const response = await createWorker(() => store).fetch(get("/api/bars/btc-usd"), testEnv());

    expect(response.status).toBe(200);
    expect(calls.filter((call) => call.name === "bars")).toEqual([{ name: "bars", params: ["BTC-USD"] }]);
  });

  it("answers 304 from KV alone when If-None-Match names the version", async () => {
    const { store, calls } = fakeStore();
    const worker = createWorker(() => store);
    await worker.fetch(get("/api/latest"), testEnv());
    const before = calls.length;

    const response = await worker.fetch(
      get("/api/overview", { headers: { "If-None-Match": '"2026-11-18T02:19:41Z"' } }),
      testEnv(),
    );

    expect(response.status).toBe(304);
    expect(calls.length).toBe(before);
  });

  it("serves a new version's body from the store again", async () => {
    const first = fakeStore();
    await createWorker(() => first.store).fetch(get("/api/runs"), testEnv());
    const second = fakeStore({ latest: LATEST.replace("02:19:41", "02:21:00"), runs: '[{"n":2}]' });
    await refresh(kvCache(testEnv().CACHE), second.store);

    const response = await createWorker(() => second.store).fetch(get("/api/runs"), testEnv());

    expect(await response.text()).toBe('[{"n":2}]');
    expect(response.headers.get("ETag")).toBe('"2026-11-18T02:21:00Z"');
  });

  it("names the version none before any run", async () => {
    const { store } = fakeStore({ latest: "null" });
    const response = await createWorker(() => store).fetch(get("/api/latest"), testEnv());

    expect(await response.text()).toBe("null");
    expect(response.headers.get("ETag")).toBe('"none"');
  });

  it("serves the body uncached when KV refuses the write", async () => {
    const { store } = fakeStore();
    const broken = {
      ...testEnv(),
      CACHE: { get: async () => null, put: async () => Promise.reject(new Error("limit")) },
    } as unknown as Env;

    const response = await createWorker(() => store).fetch(get("/api/runs"), broken);

    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  });
});

describe("unknown requests", () => {
  it.each(["/api/bars/nope", "/api/sql", "/nothing", "/api/bars/A..B"])("answers 404 for %s with no bars query", async (path) => {
    const { store, calls } = fakeStore();
    const response = await createWorker(() => store).fetch(get(path), testEnv());

    expect(response.status).toBe(404);
    expect((await response.json()) as { code: string }).toMatchObject({ code: "not_found" });
    expect(calls.filter((call) => call.name === "bars")).toEqual([]);
  });

  it("names the slug and the list in the 404 message", async () => {
    const { store } = fakeStore();
    const response = await createWorker(() => store).fetch(get("/api/bars/xyz"), testEnv());

    expect(await response.json()).toEqual({
      error: "No instrument with slug 'xyz'; see /api/overview for the list.",
      code: "not_found",
    });
  });

  it("answers 405 with Allow for a method but GET, HEAD or OPTIONS, without a store call", async () => {
    const { store, calls } = fakeStore();
    const response = await createWorker(() => store).fetch(get("/api/overview", { method: "POST" }), testEnv());

    expect(response.status).toBe(405);
    expect(response.headers.get("Allow")).toBe("GET, HEAD, OPTIONS");
    expect(calls).toEqual([]);
  });
});

describe("cross-origin reads", () => {
  it("allows the dashboard's origin and varies on Origin", async () => {
    const { store } = fakeStore();
    const response = await createWorker(() => store).fetch(get("/api/runs", { headers: { Origin: ORIGIN } }), testEnv());

    expect(response.headers.get("Access-Control-Allow-Origin")).toBe(ORIGIN);
    expect(response.headers.get("Vary")).toBe("Origin");
  });

  it("allows no other origin", async () => {
    const { store } = fakeStore();
    const response = await createWorker(() => store).fetch(
      get("/api/runs", { headers: { Origin: "https://example.com" } }),
      testEnv(),
    );

    expect(response.headers.get("Access-Control-Allow-Origin")).toBeNull();
  });

  it("answers a preflight without touching the store", async () => {
    const { store, calls } = fakeStore();
    const response = await createWorker(() => store).fetch(
      get("/api/runs", { method: "OPTIONS", headers: { Origin: ORIGIN } }),
      testEnv(),
    );

    expect(response.status).toBe(204);
    expect(response.headers.get("Access-Control-Allow-Origin")).toBe(ORIGIN);
    expect(calls).toEqual([]);
  });
});

describe("when MotherDuck fails", () => {
  it("answers 503 with Retry-After and no driver text", async () => {
    const worker = createWorker(() => async () => {
      throw new StoreUnavailableError();
    });
    const response = await worker.fetch(get("/api/overview"), testEnv());

    expect(response.status).toBe(503);
    expect(response.headers.get("Retry-After")).toBe("60");
    expect(await response.json()).toEqual({
      error: "MotherDuck did not answer; try again in a minute.",
      code: "store_unavailable",
    });
  });

  it("keeps the old version when the cron cannot reach the store", async () => {
    const { store } = fakeStore();
    await createWorker(() => store).fetch(get("/api/runs"), testEnv());
    const down = createWorker(() => async () => {
      throw new StoreUnavailableError();
    });

    await down.scheduled({} as ScheduledController, testEnv());

    expect(await kvCache(testEnv().CACHE).version()).toBe("2026-11-18T02:19:41Z");
  });
});

describe("the cron", () => {
  it("fills overview and runs under a new version, then moves it", async () => {
    const { store, calls } = fakeStore();
    const worker = createWorker(() => store);

    await worker.scheduled({} as ScheduledController, testEnv());
    const cache = kvCache(testEnv().CACHE);

    expect(await cache.version()).toBe("2026-11-18T02:19:41Z");
    expect(await cache.get("2026-11-18T02:19:41Z", "overview")).toBe(OVERVIEW);
    expect(calls.map((call) => call.name)).toEqual(["latest", "overview", "runs"]);
  });

  it("queries only latest when the version has not moved", async () => {
    const { store, calls } = fakeStore();
    const worker = createWorker(() => store);
    await worker.scheduled({} as ScheduledController, testEnv());
    calls.length = 0;

    await worker.scheduled({} as ScheduledController, testEnv());

    expect(calls.map((call) => call.name)).toEqual(["latest"]);
  });
});

describe("the docs page", () => {
  it("lists every endpoint at /", async () => {
    const { store, calls } = fakeStore();
    const response = await createWorker(() => store).fetch(get("/"), testEnv());
    const html = await response.text();

    expect(response.headers.get("Content-Type")).toContain("text/html");
    for (const path of ["/api/latest", "/api/overview", "/api/runs", "/api/bars/{slug}"]) expect(html).toContain(path);
    expect(calls).toEqual([]);
  });
});
