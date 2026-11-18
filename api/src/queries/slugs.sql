select coalesce(json_group_object(slug, ticker)::varchar, '{}') as body
from overview;
