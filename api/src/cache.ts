/** The KV adapter: bodies keyed by data version, and the version itself. */

const VERSION_KEY = "version";
const THREE_DAYS = 3 * 24 * 60 * 60;

export interface Cache {
  version(): Promise<string | null>;
  setVersion(version: string): Promise<boolean>;
  get(version: string, name: string): Promise<string | null>;
  put(version: string, name: string, body: string): Promise<boolean>;
}

/** A write that fails reports false; the body is still served uncached. */
export function kvCache(kv: KVNamespace): Cache {
  const write = async (key: string, body: string): Promise<boolean> => {
    try {
      await kv.put(key, body, { expirationTtl: THREE_DAYS });
      return true;
    } catch {
      return false;
    }
  };
  return {
    version: () => kv.get(VERSION_KEY),
    setVersion: (version) => write(VERSION_KEY, version),
    get: (version, name) => kv.get(`${version}/${name}`),
    put: (version, name, body) => write(`${version}/${name}`, body),
  };
}
