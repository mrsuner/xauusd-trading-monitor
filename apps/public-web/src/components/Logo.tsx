export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="h-7 w-7 shrink-0">
        <path
          d="M3 17.5 9.5 11l3.5 3.5L21 6"
          stroke="var(--color-primary)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M16 6h5v5"
          stroke="var(--color-primary)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {!compact && (
        <span className="text-lg font-semibold">
          Tick<span className="text-primary">Base</span> <span className="text-base-content/60">News</span>
        </span>
      )}
    </span>
  );
}
