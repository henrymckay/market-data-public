with recent as (
    select
        flagged.aligned,
        flagged.atr,
        overview.asset_class,
        flagged.close,
        flagged.day,
        flagged.direction,
        flagged.event,
        flagged.grade,
        flagged.held_to_date,
        flagged.id,
        flagged.known,
        flagged.level,
        flagged.margin_atr,
        overview.name,
        flagged.return_to_date,
        flagged.rules,
        flagged.score,
        overview.slug,
        flagged.stop,
        flagged.swing_atr,
        flagged.ticker,
        flagged.timeframe,
        flagged.trend_swings,
        flagged.volume_ratio
    from signals as flagged
    inner join overview on flagged.ticker = overview.ticker
    where flagged.known > (select max(known) from signals) - 120
    order by flagged.known desc, flagged.score desc, flagged.id
    limit 5000
)

select
    coalesce(
        to_json(
            list(
                {
                    aligned: aligned,
                    asset_class: asset_class,
                    atr: atr,
                    close: close,
                    day: day,
                    direction: direction,
                    event: event,
                    grade: grade,
                    held_to_date: held_to_date,
                    id: id,
                    known: known,
                    level: level,
                    margin_atr: margin_atr,
                    name: name,
                    return_to_date: return_to_date,
                    rules: rules,
                    score: score,
                    slug: slug,
                    stop: stop,
                    swing_atr: swing_atr,
                    ticker: ticker,
                    timeframe: timeframe,
                    trend_swings: trend_swings,
                    volume_ratio: volume_ratio
                }
                order by known desc, score desc, id
            )
        )::varchar,
        '[]'
    ) as body
from recent;
