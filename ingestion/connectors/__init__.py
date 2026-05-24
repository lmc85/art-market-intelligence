"""Connector registry for implemented open collection sources."""

from __future__ import annotations

from typing import Dict, Type

from ingestion.connectors.artic import ArtInstituteConnector
from ingestion.connectors.base import Connector
from ingestion.connectors.cleveland import ClevelandConnector
from ingestion.connectors.moma import MomaConnector
from ingestion.connectors.met import MetConnector


CONNECTORS: Dict[str, Type[Connector]] = {
    MetConnector.source_id: MetConnector,
    ArtInstituteConnector.source_id: ArtInstituteConnector,
    ClevelandConnector.source_id: ClevelandConnector,
    MomaConnector.source_id: MomaConnector,
}


def implemented_source_ids():
    return sorted(CONNECTORS)
