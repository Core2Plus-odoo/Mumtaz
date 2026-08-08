import { Card, CardHeader, FaizyLockup, StatusBadge } from "@faizy/ui";

/**
 * Scaffold only.
 *
 * The real admin panel — action-first dashboard, Orders Kanban with inline
 * assignment, Customers CRM with the slide-over detail panel and auto-
 * segmentation, Faizies roster, Applications pipeline, Analytics, the WhatsApp
 * queue view and Settings — is specified by `admin.html`, which was not in the
 * repo. Building it from guesswork would throw away the thinking already in
 * that file.
 *
 * Two things are already true and must survive the rebuild:
 *   1. Admin auth is a ROLE in the JWT (`app_metadata.role = 'admin'`), not a
 *      shared password. RLS enforces it at the database.
 *   2. The service-role key stays server-side. Privileged reads go through
 *      route handlers, never the browser client.
 */
export default function AdminHome() {
  const columns = ["pending", "assigned", "in_progress", "completed", "cancelled"] as const;

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-8 flex items-center justify-between">
        <FaizyLockup size={36} showTagline={false} />
        <span className="rounded-full bg-ink-950 px-3 py-1 text-xs font-medium text-cream-50">
          Admin
        </span>
      </header>

      <Card padding="lg">
        <CardHeader
          title="Scaffold"
          subtitle="Awaiting admin.html to rebuild the real panel — see docs/00-decisions.md §10"
        />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {columns.map((status) => (
            <div key={status} className="rounded-lg bg-cream-100 p-3">
              <StatusBadge status={status} size="sm" />
              <p className="mt-2 text-2xl font-bold tabular-nums text-content">—</p>
            </div>
          ))}
        </div>
      </Card>
    </main>
  );
}
