"""Core domain models for profile-based command practice."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Card:
    """One command practice card."""

    id: str
    module_id: str
    lesson_id: str
    prompt: str
    answers: list[str]
    explanation: str
    command: str
    tested_flags: list[str]


@dataclass(frozen=True)
class Lesson:
    """Ordered lesson containing cards."""

    id: str
    title: str
    order: int
    cards: list[Card]


@dataclass(frozen=True)
class Module:
    """Top-level learning module."""

    id: str
    title: str
    description: str
    content_version: int
    prerequisites: list[str]
    lessons: list[Lesson]
