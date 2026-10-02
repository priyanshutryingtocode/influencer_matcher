/** A placeholder block shown while real content loads.
 *
 *  Three call sites each had their own copy of the same markup and their own
 *  class set -- LoadingForm, LoadingResults and LoadingLedger were three
 *  components and three parallel CSS rules for one shimmer.
 */
export type SkeletonVariant = "form" | "results" | "ledger";

interface SkeletonProps {
  variant: SkeletonVariant;
  /** Announced instead of shown. A loading placeholder that is only visual
   *  leaves a screen-reader user with silence and no cue that work is pending. */
  label?: string;
}

export function Skeleton({ variant, label }: SkeletonProps) {
  const rows = <><span /><span /><span /></>;
  if (variant === "form") {
    return (
      <div className="skeleton-workspace">
        <div className="skeleton-rail" />
        <div className="skeleton-results">{rows}</div>
      </div>
    );
  }
  return (
    <div
      className={`skeleton-${variant}`}
      {...(label ? { "aria-live": "polite" as const, "aria-busy": "true" } : {})}
    >
      {label && <span className="visually-hidden">{label}</span>}
      {rows}
    </div>
  );
}