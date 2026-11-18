import { cn } from "../lib/cn";

interface SegmentedProps<T extends string> {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
  format?: (option: T) => string;
}

/** A row of exclusive choices, such as a period or a range. */
export function Segmented<T extends string>({ label, options, value, onChange, format }: SegmentedProps<T>) {
  return (
    <div role="group" aria-label={label} className="inline-flex min-w-0 max-w-full gap-0.5 overflow-x-auto rounded-md bg-muted p-0.5 scroll-thin">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={option === value}
          onClick={() => onChange(option)}
          className={cn(
            "h-7 min-w-9 shrink-0 rounded-[5px] px-2.5 text-sm font-medium transition-colors focus-visible:outline-offset-[-2px]",
            option === value
              ? "bg-card text-foreground shadow-[0_0_0_1px_var(--border)]"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {format === undefined ? option : format(option)}
        </button>
      ))}
    </div>
  );
}

interface SwitchProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

/** A single on/off choice drawn as a pressable button. */
export function Toggle({ label, checked, onChange }: SwitchProps) {
  return (
    <button
      type="button"
      aria-pressed={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        "h-7 shrink-0 rounded-md border px-2.5 text-sm font-medium transition-colors",
        checked ? "border-primary bg-primary/10 text-up-text" : "border-input text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}
