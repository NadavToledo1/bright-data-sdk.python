from typing import Union, List, Dict, Any
import re
import time

from .exceptions import ValidationError, APIError


class Search:

    def __init__(self, client) -> None:
        # Hold a reference to the root client for shared config / APIs.
        self._c = client

    # ---------- GPT ----------
    def gpt(
        self,
        prompt: Union[str, List[str]],
        country: Union[str, List[str]] = None,
        secondaryPrompt: Union[str, List[str]] = None,
        webSearch: Union[bool, List[bool]] = False,
        sync: bool = True,
        timeout: int = None,
    ) -> Dict[str, Any]:
        """
        Query ChatGPT via Bright Data's dataset API.

        Parameters:
        
        - prompt : str | list[str] - Prompt(s) to send.
        - country : str | list[str], optional - 2-letter uppercase ISO code per prompt (e.g., "US"). May be None.
        - secondaryPrompt : str | list[str], optional - Follow-up prompt(s) per item.
        - webSearch : bool | list[bool], default False - Enable ChatGPT web search (per prompt if list).
        - sync : bool, default True - return results immediately. False: return a snapshot_id to poll later.
        - timeout : int, optional - Default 65s (sync) / 30s (async).

        Returns: dict | list

        """
      
        # normalize prompts 
        if isinstance(prompt, str):
            prompts = [prompt]
        elif isinstance(prompt, list) and all(isinstance(p, str) for p in prompt):
            prompts = prompt
        else:
            raise ValidationError("Invalid prompt input: must be a non-empty string or list of strings.")

        if not prompts:
            raise ValidationError("At least one prompt is required.")

        # helper for normalization
        def _normalize(param, name):
            if param is None:
                return [None] * len(prompts)
            if isinstance(param, list):
                if len(param) != len(prompts):
                    raise ValidationError(f"{name} list must have the same length as prompts.")
                return param
            return [param] * len(prompts)

        countries = _normalize(country, "country")
        secondary_prompts = _normalize(secondaryPrompt, "secondary_prompt")
        web_searches = _normalize(webSearch, "web_search")

        # validation
        for c in countries:
            if c and not re.match(r"^[A-Z]{2}$", c):
                raise ValidationError(f"Invalid country code '{c}'. Must be 2 uppercase letters.")
        for s in secondary_prompts:
            if s is not None and not isinstance(s, str):
                raise ValidationError("Secondary prompts must be strings.")
        for w in web_searches:
            if not isinstance(w, bool):
                raise ValidationError("Web search flags must be boolean.")
        if timeout is not None and (not isinstance(timeout, int) or timeout <= 0):
            raise ValidationError("Timeout must be a positive integer.")

        timeout = timeout or (65 if sync else 30)

        # retry loop (API-level transient failures)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Delegate to the existing ChatGPT API client
                return self._c.chatgpt_api.scrape_chatgpt(
                    prompts=prompts,
                    countries=countries,
                    additional_prompts=secondary_prompts,
                    web_searches=web_searches,
                    sync=sync,
                    timeout=timeout,
                )
            except APIError as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                raise e

    # Web (SERP)
    def web(
        self,
        query: Union[str, List[str]],
        search_engine: str = "google",
        zone: str = None,
        response_format: str = "raw",
        method: str = "GET",
        country: str = "",
        data_format: str = "html",
        async_request: bool = False,
        max_workers: int = None,
        timeout: int = None,
        parse: bool = False,
    ):

        zone = zone or self._c.serp_zone
        max_workers = max_workers or self._c.DEFAULT_MAX_WORKERS
        # Basic validation borrowed from client.search()
        if not query:
            raise ValueError("The 'query' parameter cannot be None or empty.")
        if isinstance(query, str):
            if not query.strip():
                raise ValueError("The 'query' string cannot be empty or whitespace.")
        elif isinstance(query, list):
            if not all(isinstance(q, str) and q.strip() for q in query):
                raise ValueError("All queries in the list must be non-empty strings.")
        else:
            raise TypeError("The 'query' parameter must be a string or a list of strings.")

        return self._c.search_api.search(
            query, search_engine, zone, response_format, method, country,
            data_format, async_request, max_workers, timeout, parse
        )

    # LinkedIn 
    @property
    def linkedin(self):
        """
        Namespaced LinkedIn search helpers.

        Example:
            client.search.linkedin.posts(...)
            client.search.linkedin.jobs(...)
            client.search.linkedin.profiles(...)
        """

        return self._c.search_linkedin
