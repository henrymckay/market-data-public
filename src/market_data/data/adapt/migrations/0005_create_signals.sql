create or replace view period_bars as
select
    arg_max(adj_close, day) as adj_close,
    arg_max(close, day) as close,
    date_trunc('week', day)::date as day,
    max(high) as high,
    max(day) as last_day,
    min(low) as low,
    arg_min(open, day) as open,
    ticker,
    'w' as timeframe,
    sum(volume)::bigint as volume
from bars
group by ticker, date_trunc('week', day)::date
union all
select
    arg_max(adj_close, day) as adj_close,
    arg_max(close, day) as close,
    date_trunc('month', day)::date as day,
    max(high) as high,
    max(day) as last_day,
    min(low) as low,
    arg_min(open, day) as open,
    ticker,
    'm' as timeframe,
    sum(volume)::bigint as volume
from bars
group by ticker, date_trunc('month', day)::date;

create table pivots (
    confirmed date,
    day date,
    kind varchar,
    label varchar,
    price double,
    ticker varchar,
    timeframe varchar
);

create table signals (
    aligned boolean,
    atr double,
    close double,
    day date,
    direction varchar,
    event varchar,
    grade varchar,
    held_to_date boolean,
    id varchar,
    known date,
    level double,
    margin_atr double,
    return_to_date double,
    rules varchar,
    score integer,
    stop double,
    swing_atr double,
    ticker varchar,
    timeframe varchar,
    trend_swings integer,
    volume_ratio double
);

create table outcomes (
    end_day date,
    held boolean,
    horizon integer,
    id varchar,
    mae double,
    mfe double,
    "return" double,
    signed_return double
);

create table signal_stats (
    asset_class varchar,
    baseline_hit double,
    baseline_mean double,
    edge double,
    event varchar,
    grade varchar,
    held_rate double,
    hit_rate double,
    horizon integer,
    mae_median double,
    mean_return double,
    median_return double,
    mfe_median double,
    n bigint,
    rules varchar,
    timeframe varchar
);

create table structure (
    last_high double,
    last_low double,
    since date,
    state varchar,
    ticker varchar,
    timeframe varchar
);

alter table overview add column trend_d varchar;
alter table overview add column trend_m varchar;
alter table overview add column trend_w varchar;
