/** The MotherDuck adapter over its Postgres endpoint: one connection a query. */
import pg from "pg";
import { StoreUnavailableError } from "./error";

export type Store = (query: string, params: string[]) => Promise<string>;

export interface StoreEnv {
  MOTHERDUCK_HOST: string;
  MOTHERDUCK_DATABASE: string;
  MOTHERDUCK_TOKEN: string;
}

/** Run one query that returns one row with one `body` string. Fails with a fixed error. */
export function motherDuck(env: StoreEnv): Store {
  return async (query, params) => {
    const client = new pg.Client({
      connectionString: `postgresql://postgres:${encodeURIComponent(env.MOTHERDUCK_TOKEN)}@${env.MOTHERDUCK_HOST}:5432/${encodeURIComponent(env.MOTHERDUCK_DATABASE)}?sslmode=require`,
      connectionTimeoutMillis: 5_000,
      query_timeout: 20_000,
    });
    try {
      await client.connect();
      const result = await client.query<{ body: string }>(query, params);
      const body = result.rows[0]?.body;
      if (typeof body !== "string") throw new StoreUnavailableError();
      return body;
    } catch {
      throw new StoreUnavailableError();
    } finally {
      client.end().catch(() => undefined);
    }
  };
}
