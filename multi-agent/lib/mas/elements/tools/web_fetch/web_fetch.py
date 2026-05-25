import asyncio
from typing import Any, Dict

import safehttpx
from html_to_markdown import convert

from mas.elements.tools.common.base_tool import BaseTool
from .models import WebFetchArgs, WebFetchResponse


class WebFetchTool(BaseTool):

    name: str = "web_fetch"
    description: str = "Fetch a web page and return its content as markdown."
    args_schema = WebFetchArgs

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        return asyncio.run(self.arun(**kwargs))

    async def arun(self, **kwargs: Any) -> Dict[str, Any]:
        args = WebFetchArgs(**kwargs)
        url = str(args.url)

        try:
            response = await safehttpx.get(url, _transport=False)
        except Exception as exc:
            print(exc)
            return WebFetchResponse(success=False, url=url, error=str(exc)).model_dump()

        result = convert(response.text)
        content = result if isinstance(result, str) else result.content
        return WebFetchResponse(success=True, url=url, content=content).model_dump()
