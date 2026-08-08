import * as React from "react";
import { BLACK, ORANGE } from "@faizy/brand/tokens";

/**
 * The Faizy mark — black angular "F" monogram on a solid orange disc.
 *
 * ⚠️ HAND-BUILT FROM THE RASTER, NOT A VECTOR TRACE.
 *
 * The geometry below follows the real mark's construction — hollow angled wing
 * for the top arm, solid mid bar flowing into a bowl counter, tapering blade
 * descender to a sharp point at lower-left — but the coordinates are eyeballed
 * from a reference image, not traced. Expect a few percent of drift on edge
 * angles and terminal positions.
 *
 * TO MAKE IT DEFINITIVE (5 minutes, worth doing before launch):
 *   1. Commit the source artwork to packages/brand/assets/logo-source.png
 *   2. potrace it:
 *        convert logo-source.png -alpha remove -threshold 50% pbm:- \
 *          | potrace --svg --alphamax 0 --turdsize 8 -o traced.svg
 *      (--alphamax 0 keeps corners sharp — this mark has no curves except the
 *      rounded bar cap, and the default smoothing rounds off its points.)
 *   3. Replace the two <path> elements in FGlyph with the traced ones.
 *
 * Nothing else changes: sizing, the three colour variants, the lockup, and the
 * favicon/PWA pipeline all read from this one component.
 */

export type FaizyLogoProps = {
  /** Rendered width/height in px. The mark is square. */
  size?: number;
  /**
   * `circle`  — black F on the orange disc (default, primary usage)
   * `mono`    — single-colour F, no disc (tight or monochrome contexts)
   * `inverse` — orange F on a black disc, for cream/light surfaces where an
   *             orange disc vibrates against the warm background
   */
  variant?: "circle" | "mono" | "inverse";
  /** Only used by `mono`. Defaults to brand black. */
  monoColor?: string;
  /** Accessible name. Pass `null` for decorative use beside a visible wordmark. */
  title?: string | null;
  className?: string;
};

/**
 * The F glyph in a 0 0 1080 1080 space, matching the source artwork's canvas.
 *
 * Two paths, both fill-rule="evenodd" so their counters punch through:
 *   1. The top wing, with its long horizontal slot.
 *   2. Mid bar + bowl + descender as one connected form, with the bowl counter.
 */
function FGlyph({ fill }: { fill: string }) {
  return (
    <g fill={fill} fillRule="evenodd" clipRule="evenodd">
      {/* Top arm: angled wing, rounded cap on the lower-left, diagonal right terminal. */}
      <path
        d="M852 345 L548 345 L448 452 L302 452
           A24 24 0 0 0 302 500
           L742 500 Z
           M796 396 L566 396 L512 449 L745 449 Z"
      />
      {/* Mid bar flowing into the bowl, then the tapering blade to its point. */}
      <path
        d="M320 518 L700 518 L634 664 L494 664 L408 742 L332 845
           L430 574 L320 574
           A28 28 0 0 1 320 518 Z
           M600 582 L516 582 L474 646 L566 646 Z"
      />
    </g>
  );
}

export function FaizyLogo({
  size = 40,
  variant = "circle",
  monoColor = BLACK,
  title = "Faizy",
  className,
}: FaizyLogoProps) {
  const decorative = title === null;
  const a11y = decorative
    ? ({ "aria-hidden": true } as const)
    : ({ role: "img", "aria-label": title } as const);

  return (
    <svg
      viewBox="0 0 1080 1080"
      width={size}
      height={size}
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      {...a11y}
    >
      {variant === "circle" && (
        <>
          <circle cx="540" cy="540" r="505" fill={ORANGE} />
          <FGlyph fill={BLACK} />
        </>
      )}
      {variant === "inverse" && (
        <>
          <circle cx="540" cy="540" r="505" fill={BLACK} />
          <FGlyph fill={ORANGE} />
        </>
      )}
      {variant === "mono" && <FGlyph fill={monoColor} />}
    </svg>
  );
}

/**
 * Logo + wordmark + Urdu tagline. The standard header lockup.
 * Poppins Bold for the wordmark, per the brand system.
 */
export function FaizyLockup({
  size = 36,
  showTagline = true,
  onDark = false,
  className,
}: {
  size?: number;
  showTagline?: boolean;
  onDark?: boolean;
  className?: string;
}) {
  return (
    <div className={["flex items-center gap-2.5", className].filter(Boolean).join(" ")}>
      <FaizyLogo size={size} variant="circle" title={null} />
      <div className="flex flex-col leading-none">
        <span
          className={[
            "font-sans font-bold tracking-tight",
            onDark ? "text-cream-50" : "text-content",
          ].join(" ")}
          style={{ fontSize: size * 0.55 }}
        >
          Faizy
        </span>
        {showTagline && (
          <UrduTagline
            className={onDark ? "text-cream-200" : "text-content-muted"}
            style={{ fontSize: size * 0.34 }}
          />
        )}
      </div>
    </div>
  );
}

/**
 * The Urdu tagline: حاضر ہیں۔
 *
 * Correct rendering depends on three things, all of which are set here:
 *   1. `lang="ur"` + `dir="rtl"` so the browser applies the Urdu locale and
 *      right-to-left bidi algorithm.
 *   2. Noto Nastaliq Urdu, loaded by the app's font setup — Nastaliq needs a
 *      face built for it; falling back to a generic serif produces the flat,
 *      wrong-looking Naskh shaping.
 *   3. The string kept intact as a single unit. Never split it into characters
 *      or reverse it manually — the shaping engine does the joining, and manual
 *      handling is exactly what produces disconnected letterforms.
 *
 * Nastaliq also needs noticeably more line-height than Latin type; the
 * `leading-loose` below is deliberate, not decoration.
 */
export function UrduTagline({
  className,
  style,
}: {
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <span
      lang="ur"
      dir="rtl"
      className={["font-urdu leading-loose", className].filter(Boolean).join(" ")}
      style={style}
    >
      حاضر ہیں۔
    </span>
  );
}
