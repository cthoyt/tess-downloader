"""A client for TeSS."""

import datetime
import json
from typing import Any, Literal, cast

import click
import pydantic
import pystow
import requests
from pydantic import BaseModel, Field
from tqdm import tqdm

__all__ = [
    "INSTANCES",
    "DifficultyLevel",
    "ExternalResource",
    "LearningMaterial",
    "LearningMaterialWrapper",
    "Links",
    "Relationships",
    "Status",
    "TeSSClient",
    "Topic",
]

MODULE = pystow.module("tess")

type Records = list[dict[str, Any]]
type Status = Literal["Archived", "Published", "Active", "Draft", "Development"]
type DifficultyLevel = Literal["notspecified", "advanced", "beginner", "intermediate"]

#: Instances of TeSS. ELIXIR tries to maintain a loist
#: of known instances at https://elixirtess.github.io/docs/overview/global/
INSTANCES = {
    "tess": "https://tess.elixir-europe.org",
    "taxila": "https://taxila.nl",
    "scilifelab": "https://training.scilifelab.se",
    "dresa": "https://dresa.org.au",
    "panosc": "https://www.panosc.eu",
    "explora": "https://explora.alliancecan.ca",
    "heptraining": "https://training.cern.ch",
    "everse": "https://everse-training.app.cern.ch",
}


class Topic(BaseModel):
    """A topic."""

    preferred_label: str
    uri: str


class ExternalResource(BaseModel):
    """Links to external resources."""

    title: str
    url: str
    created_at: datetime.datetime = Field(..., serialization_alias="created-at")
    updated_at: datetime.datetime = Field(..., serialization_alias="updated-at")
    api_url: str | None = Field(None, serialization_alias="api-url")
    type: str | None = None


class LearningMaterial(BaseModel):
    """The attributes for learning materials in TeSS."""

    slug: str | None = None
    title: str
    url: str
    description: str
    keywords: list[str] | None = None
    resource_type: list[str] | None = Field(None, serialization_alias="resource-type")
    other_types: None = Field(None, serialization_alias="other-types")
    scientific_topics: list[Topic] | None = Field(None, serialization_alias="scientific-topics")
    doi: str | None | None = None
    license: str | None = Field(None, serialization_alias="licence")
    contributors: list[str] | None = None
    authors: list[str] | None = None
    contact: str | None = None
    status: Status | None = None
    version: str | None = None
    external_resources: ExternalResource | list[ExternalResource] | None = Field(
        None, serialization_alias="external-resources"
    )
    difficulty_level: DifficultyLevel = Field(
        "notspecified", serialization_alias="difficulty-level"
    )
    target_audience: list[str] | None = Field(None, serialization_alias="target-audience")
    prerequisites: str | None = None
    fields: list[str] | None = None
    learning_objectives: str | None = Field(None, serialization_alias="learning-objectives")

    date_created: datetime.date | None = Field(None, serialization_alias="date-created")
    date_modified: datetime.date | None = Field(None, serialization_alias="date-modified")
    date_published: datetime.date | None = Field(None, serialization_alias="date-published")
    last_scraped: datetime.date | None = Field(None, serialization_alias="last-scraped")
    scraper_record: bool | None = Field(None, serialization_alias="scraper-record")
    created_at: datetime.datetime | None = Field(None, serialization_alias="created-at")
    updated_at: datetime.datetime | None = Field(None, serialization_alias="updated-at")

    @pydantic.field_validator("status", mode="before")
    @classmethod
    def status_title_case(cls, value: str | None) -> str | None:
        """Fix statuses that are not in title case."""
        if isinstance(value, str):
            return value.title()
        return value

    # "operations": [],
    # "syllabus": null,
    # "subsets": [],
    # "remote-updated-date": null,
    # "remote-created-date": null,


class Relationships(BaseModel):
    """Relationships from the API."""


class Links(BaseModel):
    """Links generated for a learning material and sent by the API."""

    self: str
    redirect: str | None = None


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

    def get_material(self, slug_or_id: str | int) -> LearningMaterial:
        """Get a single material, e.g., https://tess.elixir-europe.org/materials.

        :param slug_or_id: Either a slug (in kebab case) or numeric ID for the training
            material within the TeSS instance

        :returns: A learning material

        >>> from tess_downloader import TeSSClient
        >>> client = TeSSClient()
        >>> material = client.get_material(4986)
        >>> material.title
        'Unsupervised Analysis of Bone Marrow Cells with Flexynesis'
        >>> slug = "unsupervised-analysis-of-bone-marrow-cells-with-flexynesis"
        >>> material = client.get_material(slug)
        >>> material.title
        'Unsupervised Analysis of Bone Marrow Cells with Flexynesis'
        """
        url = f"{self.base_url}/materials/{slug_or_id}.json"
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        res_json = res.json()
        return LearningMaterial.model_validate(res_json)

    def get_materials(self) -> list[LearningMaterialWrapper]:
        """Get materials, e.g., https://tess.elixir-europe.org/materials."""
        return [
            LearningMaterialWrapper.model_validate(_clean(x))
            for x in self._get_paginated("materials")
        ]

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

    def post(
        self,
        learning_material: LearningMaterial,
        *,
        email: str | None = None,
        api_key: str | None = None,
    ) -> requests.Response:
        """Post a learning material.

        :param learning_material: The learning material, which has a few fewer required
            fields from the main model (e.g., slug is not required, since TeSS assigns
            those).
        :param email: The email for the user. If not given, looks up using
            :func:`pystow.get_config` where the module is this client's ``key`` and the
            key is ``email``
        :param api_key: The API token for the user. If not given, looks up using
            :func:`pystow.get_config` where the module is this client's ``key`` and the
            key is ``api_key``

        :returns: The response from the server
        """
        url = f"{self.base_url}/materials.json"
        email = pystow.get_config(self.key, "email", raise_on_missing=True, passthrough=email)
        api_key = pystow.get_config(self.key, "api_key", raise_on_missing=True, passthrough=api_key)
        # see https://github.com/ElixirTeSS/TeSS/blob/master/docs/api.md
        headers = {
            "Accept": "application/json",
            "X-User-Token": api_key,
            "X-User-Email": email,
        }
        res = requests.post(
            url,
            timeout=15,
            json={"material": learning_material.model_dump(exclude_none=True, exclude_unset=True)},
            headers=headers,
        )
        return res


def _clean(x: dict[str, Any]) -> dict[str, Any]:
    rv = {}
    for k, v in x.items():
        if not v:
            continue
        if isinstance(v, dict):
            rv[k] = _clean(v)
        elif isinstance(v, str) and (v_stripped := v.strip()):
            rv[k] = v_stripped  # type:ignore
        else:
            rv[k] = v
    return rv
