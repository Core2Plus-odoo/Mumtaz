// Where the FAIZY ERP lives. Set at build time:
//   EXPO_PUBLIC_API_BASE=https://staging.example  EXPO_PUBLIC_ODOO_DB=faizy_staging
// There is deliberately no production default: a build must name its server.
export const API_BASE = process.env.EXPO_PUBLIC_API_BASE ?? "http://localhost:8069";
export const ODOO_DB = process.env.EXPO_PUBLIC_ODOO_DB ?? "faizy";
