select coalesce(to_json(list(overview order by ticker))::varchar, '[]') as body
from overview;
