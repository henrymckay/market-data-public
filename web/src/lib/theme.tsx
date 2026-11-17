import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Scheme = "light" | "dark";

interface ThemeValue {
  scheme: Scheme;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeValue>({ scheme: "light", toggle: () => undefined });

const current = (): Scheme => (document.documentElement.classList.contains("dark") ? "dark" : "light");

const saved = (): Scheme | null => {
  try {
    const value = localStorage.getItem("theme");
    return value === "dark" || value === "light" ? value : null;
  } catch {
    return null;
  }
};

const apply = (scheme: Scheme): void => {
  document.documentElement.classList.toggle("dark", scheme === "dark");
};

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [scheme, setScheme] = useState<Scheme>(current);

  useEffect(() => {
    const query = matchMedia("(prefers-color-scheme: dark)");
    const follow = (): void => {
      if (saved() !== null) return;
      const next = query.matches ? "dark" : "light";
      apply(next);
      setScheme(next);
    };
    query.addEventListener("change", follow);
    return () => query.removeEventListener("change", follow);
  }, []);

  const toggle = useCallback(() => {
    const next: Scheme = current() === "dark" ? "light" : "dark";
    apply(next);
    try {
      localStorage.setItem("theme", next);
    } catch {
      /* storage blocked: the choice lasts for the session */
    }
    setScheme(next);
  }, []);

  const value = useMemo(() => ({ scheme, toggle }), [scheme, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = (): ThemeValue => useContext(ThemeContext);

const ROLE_VARIABLES = {
  accent: "--primary",
  axis: "--axis",
  background: "--background",
  border: "--border",
  down: "--down",
  downText: "--down-text",
  foreground: "--foreground",
  grid: "--grid",
  muted: "--muted-foreground",
  raised: "--popover",
  sunken: "--muted",
  surface: "--card",
  text2: "--text-2",
  up: "--up",
  upText: "--up-text",
} as const;

export type Tokens = Record<keyof typeof ROLE_VARIABLES, string> & { series: string[] };

const read = (): Tokens => {
  const style = getComputedStyle(document.documentElement);
  const get = (name: string): string => style.getPropertyValue(name).trim();
  const roles = Object.fromEntries(Object.entries(ROLE_VARIABLES).map(([role, name]) => [role, get(name)]));
  const series = [1, 2, 3, 4, 5, 6, 7, 8].map((n) => get(`--chart-${n}`));
  return { ...(roles as Omit<Tokens, "series">), series };
};

/** The house roles by name, read from the page's variables, re-read when the scheme flips. */
export const useTokens = (): Tokens => {
  const { scheme } = useTheme();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- the scheme is the key
  return useMemo(read, [scheme]);
};
