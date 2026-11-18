select
    coalesce(
        to_json(
            list(
                signal_stats
                order by asset_class, event, grade, timeframe, horizon
            )
        )::varchar,
        '[]'
    ) as body
from signal_stats;
