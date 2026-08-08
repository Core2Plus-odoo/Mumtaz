import { Button, Card, CardHeader, FaizyLockup, FmbIdChip, StatusBadge, UrduTagline } from "@faizy/ui";
import { formatMoney } from "@faizy/db";

/**
 * Scaffold home screen.
 *
 * DELIBERATELY NOT the real customer home. The full feature set — family status
 * card, care-score rings, smart suggestions, care calendar, spending analytics,
 * document vault, 5-tab nav — is specified by `faizy-final.html`, which was not
 * present in the repo. Rebuilding it from guesswork would mean inventing UX the
 * brief explicitly says not to re-litigate.
 *
 * What this page IS: a live proof that the chain works end to end — brand tokens
 * → Tailwind preset → shared components → PWA shell. Replace it wholesale once
 * the prototype lands.
 */
export default function Home() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-5 px-4 pb-safe pt-8">
      <header className="flex items-center justify-between">
        <FaizyLockup size={40} />
      </header>

      <Card tone="brand" padding="lg">
        <p className="text-sm font-medium opacity-80">Design system — live</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Faizy</h1>
        <UrduTagline className="mt-1 block text-lg" />
        <p className="mt-3 text-sm leading-relaxed opacity-90">
          Brand orange <span className="font-mono">#F69E22</span> on brand black{" "}
          <span className="font-mono">#0A0A0A</span>, set in Poppins. The old blue/gold
          identity is gone.
        </p>
      </Card>

      <Card>
        <CardHeader title="Order status" subtitle="Shared across all three apps" />
        <div className="flex flex-wrap gap-2">
          <StatusBadge status="pending" />
          <StatusBadge status="assigned" />
          <StatusBadge status="in_progress" pulse />
          <StatusBadge status="completed" />
          <StatusBadge status="cancelled" />
        </div>
      </Card>

      <Card>
        <CardHeader title="Family member IDs" subtitle="Allocated by the database" />
        <div className="flex flex-wrap items-center gap-2">
          <FmbIdChip id={1} />
          <FmbIdChip id={247} />
          <FmbIdChip id="FMB-001842" copyable />
        </div>
      </Card>

      <Card>
        <CardHeader title="Plans" subtitle="Prices read from the plans table" />
        <ul className="space-y-2 text-sm">
          <li className="flex justify-between">
            <span className="text-content-muted">Lite</span>
            <span className="font-semibold">{formatMoney(2650)}</span>
          </li>
          <li className="flex justify-between">
            <span className="text-content-muted">Standard</span>
            <span className="font-semibold">{formatMoney(6620)}</span>
          </li>
          <li className="flex justify-between">
            <span className="text-content-muted">Family Pro</span>
            <span className="font-semibold">{formatMoney(11920)}</span>
          </li>
        </ul>
      </Card>

      <div className="flex flex-col gap-2">
        <Button fullWidth size="lg">
          Primary action
        </Button>
        <Button fullWidth variant="secondary">
          Secondary action
        </Button>
      </div>

      <p className="pb-6 pt-2 text-center text-xs text-content-subtle">
        Scaffold screen — replace once <code>faizy-final.html</code> is available.
      </p>
    </main>
  );
}
