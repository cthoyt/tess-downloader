"""Test getting all training materials from TeSS."""

import unittest

from tess_downloader import TeSSClient


class TestAPI(unittest.TestCase):
    """Test getting all training materials from TeSS."""

    def test_get_material(self) -> None:
        """Test getting all training materials from TeSS."""
        client = TeSSClient(key="tess", base_url="https://tess.elixir-europe.org")
        material = client.get_material(4986)
        self.assertEqual(
            "Unsupervised Analysis of Bone Marrow Cells with Flexynesis",
            material.title,
        )
