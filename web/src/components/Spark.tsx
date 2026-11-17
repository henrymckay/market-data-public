interface SparkProps {
  values: readonly number[];
  width?: number;
  height?: number;
  label: string;
  tone?: "auto" | "muted";
}

/** An inline SVG line of recent closes; coloured by whether it ended above where it began. */
export function Spark({ values, width = 80, height = 28, label, tone = "auto" }: SparkProps) {
  if (values.length < 2) return <span className="inline-block" style={{ height, width }} aria-hidden="true" />;
  let low = Infinity;
  let high = -Infinity;
  for (const v of values) {
    if (v < low) low = v;
    if (v > high) high = v;
  }
  const span = high - low || 1;
  const pad = 2;
  const step = (width - pad * 2) / (values.length - 1);
  const points = values.map((v, i) => `${(pad + i * step).toFixed(1)},${(height - pad - ((v - low) / span) * (height - pad * 2)).toFixed(1)}`);
  const rising = values[values.length - 1]! >= values[0]!;
  const color = tone === "muted" ? "var(--muted-foreground)" : rising ? "var(--up)" : "var(--down)";
  return (
    <svg role="img" aria-label={label} width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="block shrink-0">
      <polyline points={points.join(" ")} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
