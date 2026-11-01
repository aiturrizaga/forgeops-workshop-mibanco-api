"""Endpoint de salud para las probes de Kubernetes (no pasa por IG)."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
