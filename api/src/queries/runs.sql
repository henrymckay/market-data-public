with newest as (
    select
        day,
        ended,
        failed_items,
        last_day,
        outcome,
        rejected,
        requests,
        rows,
        source,
        started
    from runs
    order by ended desc
    limit 90
)

select
    coalesce(
        to_json(
            list(
                {
                    day: day,
                    ended: strftime(ended at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ'),
                    failed_items: failed_items,
                    last_day: last_day,
                    outcome: outcome,
                    rejected: rejected,
                    requests: requests,
                    rows: rows,
                    source: source,
                    started: strftime(started at time zone 'UTC', '%Y-%m-%dT%H:%M:%SZ')
                }
                order by ended desc
            )
        )::varchar,
        '[]'
    ) as body
from newest;
