select
    json_object(
        'ticker', any_value(ticker),
        'day', coalesce(list(day order by day), []::date[]),
        'open', coalesce(list(open order by day), []::double[]),
        'high', coalesce(list(high order by day), []::double[]),
        'low', coalesce(list(low order by day), []::double[]),
        'close', coalesce(list(close order by day), []::double[]),
        'adj_close', coalesce(list(adj_close order by day), []::double[]),
        'volume', coalesce(list(volume order by day), []::bigint[]),
        'dividend', coalesce(list(dividend order by day), []::double[]),
        'split', coalesce(list(split order by day), []::double[])
    )::varchar as body
from bars
where ticker = $1;
