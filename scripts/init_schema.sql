-- ==============================================================================
-- SolarLog Cloud - Optimized Ultra-Lean Database Schema
-- Zero log tables, zero bloat, pure application data only
-- ==============================================================================

-- 1. Hourly Market Prices Table (HUPX, MEMO)
CREATE TABLE IF NOT EXISTS hourly_prices (
    date DATE NOT NULL,
    hour VARCHAR(4) NOT NULL,
    price NUMERIC(10, 4) NOT NULL,
    source VARCHAR(16) NOT NULL DEFAULT 'hupx',
    PRIMARY KEY (date, hour, source)
);

-- 2. Energy Generation Table (SolarLog Hardware)
CREATE TABLE IF NOT EXISTS energy_generation (
    date DATE NOT NULL,
    hour VARCHAR(4) NOT NULL,
    energy_kwh NUMERIC(10, 4) NOT NULL,
    PRIMARY KEY (date, hour)
);

-- 3. Targeted Query Indexes
CREATE INDEX IF NOT EXISTS idx_hourly_prices_date_source ON hourly_prices (date, source);
CREATE INDEX IF NOT EXISTS idx_energy_generation_date ON energy_generation (date);

-- 4. Enable Row Level Security (RLS)
ALTER TABLE hourly_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE energy_generation ENABLE ROW LEVEL SECURITY;

-- 5. RLS Policies: Public Read Access for Frontend
DROP POLICY IF EXISTS "public_read_hourly_prices" ON hourly_prices;
CREATE POLICY "public_read_hourly_prices" ON hourly_prices FOR SELECT USING (true);

DROP POLICY IF EXISTS "public_read_energy_generation" ON energy_generation;
CREATE POLICY "public_read_energy_generation" ON energy_generation FOR SELECT USING (true);

-- 6. Write permissions for Service / Bridge
DROP POLICY IF EXISTS "service_write_hourly_prices" ON hourly_prices;
CREATE POLICY "service_write_hourly_prices" ON hourly_prices FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_write_energy_generation" ON energy_generation;
CREATE POLICY "service_write_energy_generation" ON energy_generation FOR ALL USING (true) WITH CHECK (true);
