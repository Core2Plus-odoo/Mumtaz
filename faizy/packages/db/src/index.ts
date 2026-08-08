export {
  createFaizyBrowserClient,
  createFaizyServerClient,
  createFaizyAdminClient,
} from "./client";
export type { FaizyClient } from "./client";

export { toE164, formatPhone, sendOtp, verifyOtp, roleFromSession } from "./auth";
export type { OtpChannel } from "./auth";

export {
  toMinor,
  fromMinor,
  formatMoney,
  previewOrderTotals,
  PLATFORM_FEE_RATE,
  VENDOR_COMMISSION_RATE,
} from "./money";

export {
  createOrder,
  listOrders,
  getOrder,
  subscribeToOrders,
  subscribeToWorkerOrders,
  updateOrderStatus,
  cancelOrder,
} from "./orders";
export type { CreateOrderInput } from "./orders";

export type * from "./generated/database.types";
