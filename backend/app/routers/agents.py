from fastapi import APIRouter

router = APIRouter()

AGENTS = ["agent_a", "agent_b", "agent_c", "agent_d", "agent_e", "agent_g"]


@router.get("/status")
async def agents_status():
    # TODO: estat real dels agents — Entrega 2 S3
    return {
        "agents": [
            {"id": a, "status": "stub" if a != "agent_a" else "implemented"}
            for a in AGENTS
        ]
    }
