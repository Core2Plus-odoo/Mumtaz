/**
 * Database types.
 *
 * ⚠️ HAND-WRITTEN, mirroring supabase/migrations/*.sql as verified by
 * ./scripts/verify-db.sh. The Supabase CLI generator needs Docker, which was not
 * available in the environment where these were authored.
 *
 * REGENERATE as soon as you have a project or Docker — do not maintain this by
 * hand long-term:
 *   pnpm db:types                      # from a running local Supabase
 *   supabase gen types typescript --project-id <ref> > packages/db/src/generated/database.types.ts
 *
 * Fields the database owns are marked `never` on Insert/Update where a client
 * must not set them, so the type system enforces the same rule RLS does.
 */

export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type OrderStatus = "pending" | "assigned" | "in_progress" | "completed" | "cancelled";

export type ServiceCategory =
  | "groceries"
  | "medicine"
  | "doctor_visit"
  | "documents"
  | "companionship"
  | "gift_delivery"
  | "emergency"
  | "product_request"
  | "other";

export type UserRole = "customer" | "worker" | "admin";
export type FaizyStatus = "applicant" | "active" | "suspended" | "inactive";
export type ApplicationStatus = "submitted" | "under_review" | "interview" | "approved" | "rejected";
export type PlanCode = "lite" | "standard" | "family_pro";
export type SubscriptionStatus = "trialing" | "active" | "past_due" | "cancelled" | "paused";
export type WalletTxnType = "topup" | "debit" | "refund" | "adjustment" | "payout";
export type WaMessageType =
  | "otp"
  | "booking_confirmation"
  | "faizy_assigned"
  | "status_update"
  | "receipt"
  | "generic";
export type WaStatus = "queued" | "sending" | "sent" | "delivered" | "read" | "failed";
export type DocumentType =
  | "cnic_front"
  | "cnic_back"
  | "selfie"
  | "passport"
  | "medical"
  | "receipt"
  | "proof_of_delivery"
  | "other";
export type PaymentStatus = "requires_action" | "processing" | "succeeded" | "failed" | "refunded";

export interface Profile {
  id: string;
  phone: string;
  full_name: string | null;
  email: string | null;
  country: string;
  city: string | null;
  preferred_language: "en" | "ur";
  avatar_url: string | null;
  completed_orders: number;
  free_activities_remaining: number;
  onboarding_completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FamilyMember {
  id: string;
  user_id: string;
  fmb_id: string;
  full_name: string;
  relationship: string;
  phone: string | null;
  date_of_birth: string | null;
  city: string;
  area: string | null;
  address: string | null;
  medical_notes: string | null;
  notes: string | null;
  photo_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Order {
  id: string;
  order_no: string;
  user_id: string;
  family_member_id: string | null;
  faizy_id: string | null;
  category: ServiceCategory;
  title: string;
  description: string | null;
  city: string;
  address: string | null;
  status: OrderStatus;
  scheduled_for: string | null;
  recurrence: Json | null;
  parent_order_id: string | null;
  privacy_mode: boolean;
  currency: string;
  purchase_value: number;
  platform_fee: number;
  service_fee: number;
  vendor_commission: number;
  vendor_name: string | null;
  total_amount: number;
  consumed_activity: boolean;
  assigned_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface Faizy {
  id: string;
  user_id: string | null;
  full_name: string;
  phone: string;
  cnic: string | null;
  email: string | null;
  city: string;
  areas_covered: string[];
  services: ServiceCategory[];
  status: FaizyStatus;
  is_available: boolean;
  photo_url: string | null;
  completed_orders: number;
  cancelled_orders: number;
  rating_avg: number | null;
  rating_count: number;
  base_rate_pkr: number;
  joined_at: string;
  created_at: string;
  updated_at: string;
}

export interface Plan {
  code: PlanCode;
  name: string;
  price_minor: number;
  currency: string;
  activities_included: number;
  overage_price_minor: number;
  features: string[];
  is_active: boolean;
  sort_order: number;
  gateway_price_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Subscription {
  id: string;
  user_id: string;
  plan_code: PlanCode;
  status: SubscriptionStatus;
  current_period_start: string;
  current_period_end: string;
  activities_used: number;
  activities_included: number;
  cancel_at_period_end: boolean;
  cancelled_at: string | null;
  gateway_customer_id: string | null;
  gateway_subscription_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkerOrder {
  id: string;
  order_no: string;
  category: ServiceCategory;
  title: string;
  description: string | null;
  status: OrderStatus;
  city: string;
  address: string | null;
  scheduled_for: string | null;
  assigned_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  faizy_id: string | null;
  member_name: string | null;
  fmb_id: string | null;
  member_phone: string | null;
  member_area: string | null;
  privacy_mode: boolean;
  created_at: string;
}

/** Columns a client is never allowed to write — enforced by REVOKE in 0007_rls.sql. */
type OrderServerOwned =
  | "id"
  | "order_no"
  | "purchase_value"
  | "platform_fee"
  | "service_fee"
  | "vendor_commission"
  | "total_amount"
  | "consumed_activity"
  | "faizy_id"
  | "created_at"
  | "updated_at";

export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: Profile;
        Insert: Partial<Profile> & Pick<Profile, "id" | "phone">;
        Update: Partial<Omit<Profile, "id" | "free_activities_remaining" | "completed_orders">>;
      };
      family_members: {
        Row: FamilyMember;
        Insert: Omit<FamilyMember, "id" | "fmb_id" | "created_at" | "updated_at" | "is_active"> &
          Partial<Pick<FamilyMember, "is_active">>;
        Update: Partial<Omit<FamilyMember, "id" | "fmb_id" | "user_id">>;
      };
      orders: {
        Row: Order;
        Insert: Omit<Order, OrderServerOwned | "status" | "assigned_at" | "started_at" | "completed_at" | "cancelled_at"> &
          Partial<Pick<Order, "status" | "purchase_value" | "service_fee" | "vendor_name">>;
        Update: Partial<Omit<Order, OrderServerOwned | "user_id">>;
      };
      faizies: {
        Row: Faizy;
        Insert: Omit<Faizy, "id" | "created_at" | "updated_at" | "completed_orders" | "cancelled_orders" | "rating_avg" | "rating_count">;
        Update: Partial<Pick<Faizy, "is_available" | "photo_url" | "areas_covered" | "services" | "email">>;
      };
      plans: {
        Row: Plan;
        Insert: Plan;
        Update: Partial<Plan>;
      };
      subscriptions: {
        Row: Subscription;
        Insert: never; // service-role only
        Update: never;
      };
      wallet_transactions: {
        Row: {
          id: number;
          user_id: string | null;
          faizy_id: string | null;
          order_id: string | null;
          txn_type: WalletTxnType;
          amount_minor: number;
          currency: string;
          balance_note: string | null;
          reference: string | null;
          created_at: string;
        };
        Insert: never; // service-role only
        Update: never;
      };
      activity_ledger: {
        Row: {
          id: number;
          user_id: string;
          order_id: string | null;
          subscription_id: string | null;
          source: "free" | "included" | "overage";
          amount_minor: number;
          currency: string;
          note: string | null;
          created_at: string;
        };
        Insert: never;
        Update: never;
      };
    };
    Views: {
      worker_orders: { Row: WorkerOrder };
    };
    Functions: {
      consume_activity: { Args: { p_order_id: string }; Returns: string };
      wallet_balance_minor: { Args: { p_user_id: string }; Returns: number };
      approve_faizy_application: { Args: { p_application_id: string }; Returns: string };
      check_application_status: {
        Args: { p_reference_no: string; p_phone: string };
        Returns: { reference_no: string; status: ApplicationStatus; submitted_at: string }[];
      };
    };
    Enums: {
      order_status: OrderStatus;
      service_category: ServiceCategory;
      user_role: UserRole;
      plan_code: PlanCode;
    };
  };
}
