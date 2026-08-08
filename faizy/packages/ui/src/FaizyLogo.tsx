import * as React from "react";
import { BLACK, ORANGE } from "@faizy/brand/tokens";

/**
 * ⚠️ INTERIM MARK — must be replaced before launch.
 *
 * This is a geometric reconstruction built to the written description of the
 * live Faizy mark (bold black angular "F" with flag/speed-line styling, on a
 * solid orange circle). It is NOT a trace of the official artwork.
 *
 * To finish this properly: drop the source PNG from facebook.com/faizy.pk into
 * `packages/brand/assets/logo-source.png`, trace it to clean vectors, and replace
 * the paths below. Everything else — sizing, colour handling, the lockup, the
 * favicon/PWA icon pipeline — is already wired, so it is a paths-only swap.
 *
 * See packages/brand/README.md.
 */

export type FaizyLogoProps = {
  /** Rendered width/height in px. The mark is square. */
  size?: number;
  /**
   * `circle`  — black F on the orange disc (default, primary usage)
   * `mono`    — single-colour F, no disc (for tight/monochrome contexts)
   * `inverse` — orange F on black disc (for use on cream/light surfaces where
   *             an orange disc would vibrate against a warm background)
   */
  variant?: "circle" | "mono" | "inverse";
  /** Only used by `mono`. Defaults to brand black. */
  monoColor?: string;
  /** Accessible name. Pass `null` for decorative use beside a visible wordmark. */
  title?: string | null;
  className?: string;
};

/** The F glyph itself, in a 0 0 100 100 space. Shared by every variant. */
function FGlyph({ fill }: { fill: string }) {
  return (
    <g fill={fill}>
      {/* Stem — leans right at the top for forward motion. */}
      <polygon points="40,24 54,24 46,76 32,76" />
      {/* Top arm. */}
      <polygon points="42,24 78,24 75.5,37 39.5,37" />
      {/* Mid arm — shorter, per standard F proportions. */}
      <polygon points="36.5,45 67,45 64.5,58 34,58" />
      {/* Speed lines trailing the stem, aligned to the arms. */}
      <polygon points="14,45 30,45 27.5,58 11.5,58" />
      <polygon points="21,24 36,24 33.5,37 18.5,37" />
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
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      {...a11y}
    >
      {variant === "circle" && (
        <>
          <circle cx="50" cy="50" r="50" fill={ORANGE} />
          <FGlyph fill={BLACK} />
        </>
      )}
      {variant === "inverse" && (
        <>
          <circle cx="50" cy="50" r="50" fill={BLACK} />
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
      <FaizyLogo size={size} variant={onDark ? "circle" : "circle"} title={null} />
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
