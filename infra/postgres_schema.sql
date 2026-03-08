create table if not exists market_snapshots (
  id bigserial primary key,
  symbol text not null,
  ts timestamptz not null,
  price numeric,
  volume numeric,
  source text
);

create table if not exists news_events (
  id bigserial primary key,
  symbol text,
  ts timestamptz not null,
  headline text,
  sentiment_label text,
  sentiment_score numeric
);

create table if not exists model_registry (
  id bigserial primary key,
  model_name text not null,
  version text not null,
  sharpe numeric,
  sortino numeric,
  max_drawdown numeric,
  created_at timestamptz not null default now()
);

create table if not exists experiments (
  id bigserial primary key,
  kind text not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists audit_events (
  id bigserial primary key,
  kind text not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);
