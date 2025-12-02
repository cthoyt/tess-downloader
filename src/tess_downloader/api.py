"""A client for TeSS."""

import json
from typing import Any, Literal, cast

import click
import pystow
import requests
from pydantic import BaseModel, Field
from tqdm import tqdm

__all__ = [
    "INSTANCES",
    "LearningMaterial",
    "TeSSClient",
]

MODULE = pystow.module("tess")

type Records = list[dict[str, Any]]

#: Instances of TESS
INSTANCES = {
    "tess": "https://tess.elixir-europe.org",
    "taxila": "https://taxila.nl",
    "scilifelab": "https://training.scilifelab.se",
    "dresa": "https://dresa.org.au",
    "panosc": "https://www.panosc.eu",
}


class Topic(BaseModel):
    """A topic."""

    label: str = Field(serialization_alias="preferred-label")
    uri: str


class LearningMaterial(BaseModel):
    """The attributes for learning materials in TeSS."""

    slug: str
    title: str
    url: str
    description: str
    keywords: list[str] | None = None
    resource_type: list[str] | None = Field(None, serialization_alias="resource-type")
    other_types: None = Field(None, serialization_alias="other-types")
    scientific_topics: list[Topic] | None = Field(None, serialization_alias="scientific-topics")
    doi: str | None | None = None
    licence: str | None = None
    contributors: list[str] | None = None
    authors: list[str] | None = None
    contact: str | None = None
    status: Literal["Archived", "Published", "Active"] | None = None
    version: str | None = None
    external_resources: list[str] | None = Field(None, serialization_alias="external-resources")
    difficult_level: Literal["notspecified", "advanced", "beginner", "intermediate"] = Field(
        "notspecified", serialization_alias="scientific-topics"
    )
    target_audience: list[str] | None = Field(None, serialization_alias="target-audience")
    prerequisites: list[str] | None = None
    fields: list[str] | None = None
    learning_objectives: str | None = Field(None, serialization_alias="learning-objectives")

    # "operations": [],
    # "syllabus": null,
    # "subsets": [],
    # "date-created": "2022-10-11",
    # "date-modified": "2025-06-11",
    # "date-published": "2025-05-05",
    # "remote-updated-date": null,
    # "remote-created-date": null,
    # "last-scraped": "2025-06-18",
    # "scraper-record": true,
    # "created-at": "2025-06-18T05:33:14.781Z",
    # "updated-at": "2025-06-18T05:33:14.781Z"


class Relationships(BaseModel):
    """Relationships from the API."""


class Links(BaseModel):
    """Links generated for a learning material and sent by the API."""

    self: str
    redirect: str


class LearningMaterialWrapper(BaseModel):
    """Represents a Learning Material in TeSS."""

    id: str
    attributes: LearningMaterial
    relationships: Relationships | None = None
    links: Links | None = None


class TeSSClient:
    """A client to a TeSS instance."""

    def __init__(self, key: str = "tess", base_url: str | None = None) -> None:
        """Initialize the TeSS client."""
        self.key = key
        if base_url is None:
            if key not in INSTANCES:
                raise ValueError(
                    f"base_url needs to be given if it can't be looked up from {INSTANCES}"
                )
            base_url = INSTANCES[key]
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

    def post(self, payload: LearningMaterialWrapper, api_key: str | None) -> requests.Response:
        """Post a learning material."""
        url = f"{self.base_url}/materials"
        api_key = pystow.get_config("tess", "api_key", raise_on_missing=True, passthrough=api_key)
        headers = {
            "Accept": "application/json",
            "Authorization": api_key,
        }
        res = requests.post(
            url,
            timeout=15,
            json=payload.model_dump(exclude_none=True, exclude_unset=True),
            headers=headers,
            # TODO where to put the API key?
        )
        return res


def _main() -> None:
    payload = LearningMaterialWrapper(
        id="12345",
        attributes=LearningMaterial(
            slug="test-dalia-export",
            title="Test title",
            url="https://example.org/test",
            description="Test description",
            authors=["Charles Tapley Hoyt"],
        ),
    )

    base_url = "https://test.tesshub.hzdr.de"
    key = pystow.get_config("panosc", "test_key", raise_on_missing=True)
    api_token = pystow.get_config("panosc", "test_api_token")
    client = TeSSClient(key=key, base_url=base_url)
    res = client.post(payload, api_key=api_token)
    res.raise_for_status()
    click.echo(json.dumps(res.json(), indent=2))


if __name__ == "__main__":
    _main()
