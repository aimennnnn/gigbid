"""Loads agent/config.yaml once and answers "which model does this node use?".

No model name, budget or rule is hard-coded anywhere else in the project.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).with_name("config.yaml")


class Settings:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw
        # Environment variables win over the file, so Docker can switch profile.
        self.profile_name: str = os.getenv("GIGBID_PROFILE", raw["profile"])
        self.marketplace: str = os.getenv("GIGBID_MARKETPLACE", raw["marketplace"])
        if self.profile_name not in raw["profiles"]:
            raise ValueError(f"unknown profile: {self.profile_name}")
        if self.marketplace not in ("gigsim", "upwork"):
            raise ValueError(f"unknown marketplace: {self.marketplace}")
        if raw["autonomy"]["auto_send"]:
            raise ValueError("autonomy.auto_send must be false: nothing is sent without approval")

    @property
    def profile(self) -> dict[str, Any]:
        return self.raw["profiles"][self.profile_name]

    def node(self, name: str) -> dict[str, Any]:
        """Settings for one agent node, with its model size turned into a real model name."""
        cfg = dict(self.raw["nodes"][name])
        cfg["model_name"] = self.profile["models"][cfg["model"]]
        cfg["fallback_model_name"] = self.profile["models"]["fallback"]
        return cfg

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]


@lru_cache
def get_settings() -> Settings:
    return Settings(yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")))
