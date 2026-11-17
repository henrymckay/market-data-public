import type { ReactNode } from "react";

import { cn } from "../lib/cn";

interface CardProps {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function Card({ title, subtitle, actions, className, children }: CardProps) {
  return (
    <section className={cn("min-w-0 rounded-lg border bg-card p-3 sm:p-4", className)}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h2 className="m-0 text-lg font-semibold">{title}</h2>
          {subtitle !== undefined && <p className="m-0 text-sm text-muted-foreground">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}
