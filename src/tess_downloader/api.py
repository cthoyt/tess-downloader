"""A client for TeSS."""

import json
from typing import Any, cast

import click
import pystow
import requests
from tqdm import tqdm

__all__ = [
    "TeSSClient",
]

MODULE = pystow.module("tess")

type Records = list[dict[str, Any]]


class TeSSClient:
    """A client to a TeSS instance."""

    def __init__(
        self, key: str = "tess", base_url: str = "https://tess.elixir-europe.org/"
    ) -> None:
        """Initialize the TeSS client."""
        self.key = key
        self.module = MODULE.module(self.key)
        self.raw_module = self.module.module("raw")
        self.base_url = base_url.rstrip("/")

    def _get_paginated(self, endpoint: str, *, force: bool = False) -> Records:
        full_path = self.raw_module.join(name=f"{endpoint}.json")
        if full_path.exists() and not force:
            with full_path.open() as file:
                return cast(Records, json.load(file))

        url = f"{self.base_url}/{endpoint}.json_api"
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            tqdm.write(
                click.style(
                    f"[{self.key} - {endpoint}] failed with status {res.status_code} on {url}",
                    fg="red",
                )
            )
            return []

        data = []
        res_json = res.json()

        if "data" not in res_json:
            tqdm.write(click.style(f"[{self.key} - {endpoint}] failed: {res_json}", fg="red"))
            return []

        first_path = self.raw_module.join(f"{endpoint}-parts", name=f"{endpoint}_1.json")
        with first_path.open("w") as file:
            json.dump(res_json["data"], file, indent=2, ensure_ascii=False)

        data.extend(res_json["data"])

        try:
            total = int(res_json["links"]["last"].split("=")[1])
        except ValueError:
            # TODO need more principled URL parameter parsing
            total = None
        except KeyError:
            # missing 'last', happens for short lists < 10 long
            total = None

        with tqdm(total=total, desc=f"Downloading {endpoint}", unit="page") as bar:
            bar.update(1)

            while "next" in res_json["links"]:
                bar.update(1)
                page = res_json["links"]["next"].split("=")[1]
                res_json = requests.get(url, timeout=15, params={"page_number": page}).json()
                loop_path = self.raw_module.join(
                    f"{endpoint}-parts", name=f"{endpoint}_{page}.json"
                )
                with loop_path.open("w") as file:
                    json.dump(res_json["data"], file, indent=2, ensure_ascii=False)

                data.extend(res_json["data"])

        with full_path.open("w") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

        return data

    def get_events(self) -> Records:
        """Get events, e.g., https://tess.elixir-europe.org/events."""
        return self._get_paginated("events")

    def get_materials(self) -> Records:
        """Get materials, e.g., https://tess.elixir-europe.org/materials."""
        return self._get_paginated("materials")

    def get_elearning_materials(self) -> Records:
        """Get eLearning materials, e.g., https://tess.elixir-europe.org/elearning_materials."""
        return self._get_paginated("elearning_materials")

    def get_workflows(self) -> Records:
        """Get workflows, e.g., https://tess.elixir-europe.org/workflows."""
        return self._get_paginated("workflows")

    def get_collections(self) -> Records:
        """Get collections, e.g., https://tess.elixir-europe.org/collections."""
        return self._get_paginated("collections")

    def get_learning_paths(self) -> Records:
        """Get learning paths, e.g., https://tess.elixir-europe.org/learning_paths."""
        return self._get_paginated("learning_paths")

    def get_content_providers(self) -> Records:
        """Get content providers, e.g., https://tess.elixir-europe.org/content_providers."""
        return self._get_paginated("content_providers")

    def get_nodes(self) -> Records:
        """Get nodes, e.g., https://tess.elixir-europe.org/nodes."""
        return self._get_paginated("nodes")

    def cache(self) -> None:
        """Cache all parts of TeSS."""
        self.get_events()
        self.get_materials()
        self.get_elearning_materials()
        self.get_workflows()
        self.get_collections()
        self.get_learning_paths()
        self.get_content_providers()
        self.get_nodes()
