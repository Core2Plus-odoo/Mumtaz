import { Button, Card, CardHeader, FaizyLockup, UrduTagline } from "@faizy/ui";

/**
 * Scaffold only.
 *
 * The worker app is a NEW build (there is no prototype to follow), so the shape
 * is an open question rather than a missing file. Per docs/00-decisions.md §4:
 *
 *   * It is a PWA, not React Native — camera capture and geolocation both work
 *     on the web, and shipping fixes without a Play Store review cycle matters
 *     more for a field-ops app you will iterate on weekly.
 *   * The core loop should ALSO work entirely inside WhatsApp (receive
 *     assignment → reply to accept → send photo). These workers already live in
 *     WhatsApp; an app is a new thing to install and remember. The DB layer is
 *     deliberately agnostic about which surface writes the status change.
 *
 * Screens to build: assigned jobs, accept/start/complete with photo proof,
 * earnings and payouts, availability toggle.
 */
export default function WorkerHome() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-5 px-4 pb-safe pt-8">
      <header className="flex items-center justify-between">
        <FaizyLockup size={36} showTagline={false} />
        <span className="rounded-full bg-orange-100 px-3 py-1 text-xs font-medium text-orange-800">
          Worker
        </span>
      </header>

      <Card tone="inverse" padding="lg">
        <p className="text-sm font-medium opacity-70">Faizy Worker</p>
        <UrduTagline className="mt-1 block text-2xl text-orange-500" />
        <p className="mt-3 text-sm leading-relaxed opacity-80">
          Scaffold. Jobs, photo proof, earnings and the availability toggle land once the
          data layer is pointed at a live Supabase project.
        </p>
      </Card>

      <Card>
        <CardHeader title="Availability" subtitle="Controls whether you get assigned work" />
        <Button fullWidth variant="secondary">
          Go online
        </Button>
      </Card>
    </main>
  );
}
