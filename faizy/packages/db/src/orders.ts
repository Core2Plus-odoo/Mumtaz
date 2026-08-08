import type { FaizyClient } from "./client";
import type { Order, OrderStatus, ServiceCategory } from "./generated/database.types";

/**
 * Order reads, writes, and realtime.
 *
 * Note what is NOT here: nothing sets prices, assigns a Faizy, or counts an
 * activity. Those columns are REVOKEd from `authenticated` in the RLS migration
 * and computed by database triggers, so they are unreachable from client code by
 * construction rather than by convention.
 */

export type CreateOrderInput = {
  familyMemberId?: string | null;
  category: ServiceCategory;
  title: string;
  description?: string;
  city: string;
  address?: string;
  scheduledFor?: Date | null;
  /** Hides notes and member identity from the assigned Faizy. */
  privacyMode?: boolean;
  recurrence?: { freq: "daily" | "weekly" | "monthly"; interval: number; until?: string } | null;
};

export async function createOrder(
  client: FaizyClient,
  userId: string,
  input: CreateOrderInput,
): Promise<{ order: Order } | { error: string }> {
  const { data, error } = await client
    .from("orders")
    .insert({
      user_id: userId,
      family_member_id: input.familyMemberId ?? null,
      category: input.category,
      title: input.title,
      description: input.description ?? null,
      city: input.city,
      address: input.address ?? null,
      scheduled_for: input.scheduledFor?.toISOString() ?? null,
      privacy_mode: input.privacyMode ?? false,
      recurrence: input.recurrence ?? null,
    } as never)
    .select()
    .single();

  if (error) return { error: error.message };
  return { order: data as Order };
}

export async function listOrders(
  client: FaizyClient,
  userId: string,
  opts: { status?: OrderStatus[]; limit?: number } = {},
): Promise<Order[]> {
  let query = client
    .from("orders")
    .select("*")
    .eq("user_id", userId)
    .order("created_at", { ascending: false })
    .limit(opts.limit ?? 50);

  if (opts.status?.length) query = query.in("status", opts.status);

  const { data, error } = await query;
  if (error) throw new Error(`Failed to load orders: ${error.message}`);
  return (data ?? []) as Order[];
}

export async function getOrder(client: FaizyClient, orderId: string): Promise<Order | null> {
  const { data, error } = await client.from("orders").select("*").eq("id", orderId).maybeSingle();
  if (error) throw new Error(`Failed to load order: ${error.message}`);
  return (data as Order | null) ?? null;
}

/**
 * Live order updates.
 *
 * This is what delivers the sub-2-second requirement: an admin moving a card in
 * the Kanban writes the row, and Postgres change-data-capture pushes it to the
 * customer's phone without polling.
 *
 * RLS applies to realtime too, so a customer only ever receives their own rows —
 * but the filter is still set server-side to avoid shipping irrelevant traffic.
 *
 * Returns an unsubscribe function; call it on unmount or you will leak channels
 * across navigations.
 */
export function subscribeToOrders(
  client: FaizyClient,
  userId: string,
  onChange: (order: Order, event: "INSERT" | "UPDATE" | "DELETE") => void,
): () => void {
  const channel = client
    .channel(`orders:${userId}`)
    .on(
      "postgres_changes",
      { event: "*", schema: "public", table: "orders", filter: `user_id=eq.${userId}` },
      (payload) => {
        const row = (payload.new ?? payload.old) as Order;
        onChange(row, payload.eventType as "INSERT" | "UPDATE" | "DELETE");
      },
    )
    .subscribe();

  return () => {
    void client.removeChannel(channel);
  };
}

/** Live updates for a single Faizy's assigned work, for the worker app. */
export function subscribeToWorkerOrders(
  client: FaizyClient,
  faizyId: string,
  onChange: () => void,
): () => void {
  const channel = client
    .channel(`worker-orders:${faizyId}`)
    .on(
      "postgres_changes",
      { event: "*", schema: "public", table: "orders", filter: `faizy_id=eq.${faizyId}` },
      () => onChange(),
    )
    .subscribe();

  return () => {
    void client.removeChannel(channel);
  };
}

/** Worker-side status transitions. RLS restricts these to the assigned Faizy. */
export async function updateOrderStatus(
  client: FaizyClient,
  orderId: string,
  status: Extract<OrderStatus, "in_progress" | "completed">,
): Promise<{ ok: true } | { error: string }> {
  const { error } = await client.from("orders").update({ status } as never).eq("id", orderId);
  if (error) return { error: error.message };
  return { ok: true };
}

export async function cancelOrder(
  client: FaizyClient,
  orderId: string,
  reason: string,
): Promise<{ ok: true } | { error: string }> {
  const { error } = await client
    .from("orders")
    .update({ status: "cancelled", cancellation_reason: reason } as never)
    .eq("id", orderId);
  if (error) return { error: error.message };
  return { ok: true };
}
