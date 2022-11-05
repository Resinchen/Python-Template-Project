import json
import re
from functools import partial

from pydantic.json import custom_pydantic_encoder

JsonSerializer = partial(
    json.dumps,
    ensure_ascii=False,
    indent=True,
    default=partial(custom_pydantic_encoder, {type(re.compile('')): lambda v: v.pattern}),
)
