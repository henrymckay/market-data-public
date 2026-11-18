/** The one error the store raises, with a fixed message: no driver text, no token. */
export class StoreUnavailableError extends Error {
  constructor() {
    super("store unavailable");
  }
}
