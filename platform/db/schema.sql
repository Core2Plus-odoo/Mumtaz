-- =====================================================================
--  Mumtaz Platform — Control-plane schema (PostgreSQL)
--  DB: mumtaz_platform   Owner: mumtaz_admin
--  Idempotent: safe to re-run. No secrets here.
-- =====================================================================

CREATE TABLE IF NOT EXISTS tenants (
    id              SERIAL PRIMARY KEY,
    slug            VARCHAR(80) UNIQUE NOT NULL,
    name            VARCHAR(255) NOT NULL,
    type            VARCHAR(20)  NOT NULL DEFAULT 'business',   -- business | org | org_sme
    status          VARCHAR(20)  NOT NULL DEFAULT 'provisioning', -- provisioning|trial|active|suspended|cancelled
    plan            VARCHAR(40)  DEFAULT 'starter',
    odoo_db         VARCHAR(120),
    parent_org_id   INTEGER REFERENCES tenants(id),
    country         VARCHAR(60)  DEFAULT 'UAE',
    currency        VARCHAR(5)   DEFAULT 'AED',
    industry        VARCHAR(80)  DEFAULT 'Trading',
    mrr_usd         NUMERIC(10,2) DEFAULT 0,
    -- White-label (org tenants). Brand defaults = Mumtaz gold/ink (not hardcoded teal).
    wl_name             VARCHAR(255),
    wl_logo_url         TEXT,
    wl_primary_color    VARCHAR(7) DEFAULT '#B8862A',
    wl_secondary_color  VARCHAR(7) DEFAULT '#1C1917',
    wl_subdomain        VARCHAR(120),
    wl_custom_domain    VARCHAR(255),
    wl_tagline          VARCHAR(255),
    trial_ends_at   TIMESTAMPTZ,
    activated_at    TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS platform_users (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER REFERENCES tenants(id),
    email           VARCHAR(255) UNIQUE NOT NULL,
    name            VARCHAR(255) NOT NULL,
    first_name      VARCHAR(100),
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(30)  NOT NULL DEFAULT 'owner',  -- super_admin|owner|admin|member|viewer
    is_super_admin  BOOLEAN DEFAULT FALSE,
    status          VARCHAR(20) DEFAULT 'active',
    last_login      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Dynamic module catalogue — the single source of truth for products & pricing.
-- Prices are editable rows (NOT hardcoded in app code).
CREATE TABLE IF NOT EXISTS module_catalogue (
    id          SERIAL PRIMARY KEY,
    key         VARCHAR(80) UNIQUE NOT NULL,
    name        VARCHAR(120) NOT NULL,
    description TEXT,
    icon        VARCHAR(10) DEFAULT '📦',
    category    VARCHAR(60) DEFAULT 'core',
    price_usd   NUMERIC(8,2) DEFAULT 0,
    price_aed   NUMERIC(8,2) DEFAULT 0,
    is_free     BOOLEAN DEFAULT FALSE,
    is_core     BOOLEAN DEFAULT FALSE,
    odoo_module VARCHAR(120),
    sort_order  INTEGER DEFAULT 100,
    active      BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS tenant_modules (
    id           SERIAL PRIMARY KEY,
    tenant_id    INTEGER REFERENCES tenants(id),
    module_id    INTEGER REFERENCES module_catalogue(id),
    status       VARCHAR(20) DEFAULT 'active',
    activated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, module_id)
);

CREATE TABLE IF NOT EXISTS billing_invoices (
    id           SERIAL PRIMARY KEY,
    tenant_id    INTEGER REFERENCES tenants(id),
    invoice_ref  VARCHAR(40) UNIQUE,
    amount_usd   NUMERIC(10,2) NOT NULL,
    currency     VARCHAR(5) DEFAULT 'USD',
    status       VARCHAR(20) DEFAULT 'pending',
    period_start DATE,
    period_end   DATE,
    due_date     DATE,
    paid_at      TIMESTAMPTZ,
    line_items   JSONB DEFAULT '[]',
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS activity_log (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   INTEGER REFERENCES tenants(id),
    user_id     INTEGER REFERENCES platform_users(id),
    action      VARCHAR(120) NOT NULL,
    entity_type VARCHAR(80),
    entity_id   VARCHAR(80),
    details     JSONB DEFAULT '{}',
    ip_address  VARCHAR(45),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS zaki_kb (
    id         BIGSERIAL PRIMARY KEY,
    tenant_id  INTEGER REFERENCES tenants(id),
    category   VARCHAR(60),
    title      VARCHAR(255),
    content    TEXT,
    importance INTEGER DEFAULT 2,
    source     VARCHAR(60) DEFAULT 'chat',
    archived   BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS marketplace_listings (
    id           SERIAL PRIMARY KEY,
    tenant_id    INTEGER REFERENCES tenants(id),
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    category     VARCHAR(80),
    unit_price   NUMERIC(12,2),
    currency     VARCHAR(5) DEFAULT 'AED',
    unit         VARCHAR(40) DEFAULT 'unit',
    min_qty      NUMERIC(10,2) DEFAULT 1,
    delivery_days INTEGER DEFAULT 3,
    rating       NUMERIC(3,2) DEFAULT 5.0,
    review_count INTEGER DEFAULT 0,
    verified     BOOLEAN DEFAULT FALSE,
    active       BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS marketplace_orders (
    id               SERIAL PRIMARY KEY,
    listing_id       INTEGER REFERENCES marketplace_listings(id),
    buyer_tenant_id  INTEGER REFERENCES tenants(id),
    seller_tenant_id INTEGER REFERENCES tenants(id),
    quantity         NUMERIC(12,2),
    unit_price       NUMERIC(12,2),
    total_amount     NUMERIC(12,2),
    platform_fee     NUMERIC(12,2),
    status           VARCHAR(30) DEFAULT 'pending',
    buyer_po_ref     VARCHAR(80),
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tenants_slug    ON tenants(slug);
CREATE INDEX IF NOT EXISTS idx_tenants_status  ON tenants(status);
CREATE INDEX IF NOT EXISTS idx_tenants_type    ON tenants(type);
CREATE INDEX IF NOT EXISTS idx_tenants_parent  ON tenants(parent_org_id);
CREATE INDEX IF NOT EXISTS idx_users_email     ON platform_users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant    ON platform_users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tmods_tenant    ON tenant_modules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_billing_tenant  ON billing_invoices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_log_tenant      ON activity_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_log_time        ON activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_kb_tenant       ON zaki_kb(tenant_id);
CREATE INDEX IF NOT EXISTS idx_listing_tenant  ON marketplace_listings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_order_buyer     ON marketplace_orders(buyer_tenant_id);
