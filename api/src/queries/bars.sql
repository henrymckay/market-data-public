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
        'split', coalesce(list(split order by day), []::double[]),
        'weekly', (
            select
                json_object(
                    'day', coalesce(list(day order by day), []::date[]),
                    'open', coalesce(list(open order by day), []::double[]),
                    'high', coalesce(list(high order by day), []::double[]),
                    'low', coalesce(list(low order by day), []::double[]),
                    'close', coalesce(list(close order by day), []::double[]),
                    'adj_close', coalesce(list(adj_close order by day), []::double[]),
                    'volume', coalesce(list(volume order by day), []::bigint[])
                )
            from period_bars
            where ticker = $1 and timeframe = 'w'
        ),
        'monthly', (
            select
                json_object(
                    'day', coalesce(list(day order by day), []::date[]),
                    'open', coalesce(list(open order by day), []::double[]),
                    'high', coalesce(list(high order by day), []::double[]),
                    'low', coalesce(list(low order by day), []::double[]),
                    'close', coalesce(list(close order by day), []::double[]),
                    'adj_close', coalesce(list(adj_close order by day), []::double[]),
                    'volume', coalesce(list(volume order by day), []::bigint[])
                )
            from period_bars
            where ticker = $1 and timeframe = 'm'
        ),
        'pivots', coalesce(
            (
                select
                    list(
                        {
                            timeframe: timeframe,
                            kind: kind,
                            label: label,
                            day: day,
                            price: price,
                            confirmed: confirmed
                        }
                        order by timeframe, day, kind
                    )
                from pivots
                where ticker = $1
            ),
            []
        ),
        'signals', coalesce(
            (
                select
                    list(
                        {
                            id: id,
                            timeframe: timeframe,
                            event: event,
                            day: day,
                            known: known,
                            level: level,
                            stop: stop,
                            grade: grade,
                            score: score
                        }
                        order by day, id
                    )
                from signals
                where ticker = $1
            ),
            []
        )
    )::varchar as body
from bars
where ticker = $1;
