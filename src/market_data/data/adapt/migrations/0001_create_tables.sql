create table bars (
    adj_close double,
    close double,
    day date,
    dividend double,
    fetched timestamp with time zone,
    high double,
    low double,
    open double,
    split double,
    ticker varchar,
    volume bigint
);

create table rejected (
    day date,
    fetched timestamp with time zone,
    reason varchar,
    record varchar,
    ticker varchar
);

create table tickers (
    active boolean,
    asset_class varchar,
    name varchar,
    quote_type varchar,
    sector varchar,
    ticker varchar
);

create table runs (
    day date,
    ended timestamp with time zone,
    failed_items integer,
    last_day date,
    outcome varchar,
    rejected integer,
    requests integer,
    rows bigint,
    source varchar,
    started timestamp with time zone
);
