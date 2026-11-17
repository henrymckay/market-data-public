import { useEffect } from "react";

/** Mirror a screen's readiness on the root: `data-ready` is 1 once its data has drawn. */
export const useReady = (done: boolean): void => {
  useEffect(() => {
    const root = document.documentElement;
    if (!done) {
      root.dataset.ready = "0";
      return undefined;
    }
    let frame = requestAnimationFrame(() => {
      frame = requestAnimationFrame(() => {
        root.dataset.ready = "1";
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [done]);
};
