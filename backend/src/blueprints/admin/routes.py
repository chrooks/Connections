"""
Admin API endpoints for puzzle pool management.

Blueprint prefix: /admin
Registered in app.py alongside the main /connections blueprint.

These endpoints are not authenticated — add auth middleware before exposing
them to the public internet.
"""

import logging

from flask import Blueprint, request

from ...services.utils import create_response

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/generate-puzzles", methods=["POST"])
def queue_puzzle_generation():
    """
    Queue puzzle generation jobs.

    Request body (JSON):
        {
            "count":       int,   required — number of jobs to queue (1–50)
            "config_name": str    optional — puzzle config slug, defaults to "classic"
        }

    Response (201):
        {
            "data": {
                "job_ids":     [uuid, ...],
                "count":       int,
                "config_name": str
            }
        }
    """
    body = request.get_json(silent=True) or {}
    count = body.get("count")
    config_name = body.get("config_name", "classic")

    if not isinstance(count, int) or count < 1:
        return create_response(
            error="'count' must be a positive integer",
            status_code=400,
        )
    if count > 50:
        return create_response(
            error="'count' must not exceed 50 per request",
            status_code=400,
        )

    from ...services.puzzle_pool_service import _get_client

    client = _get_client()

    # Resolve config_id from the human-readable name.
    cfg_result = (
        client.table("puzzle_configs")
        .select("id")
        .eq("name", config_name)
        .single()
        .execute()
    )
    if not cfg_result.data:
        return create_response(
            error=f"Unknown config_name: '{config_name}'",
            status_code=404,
        )

    config_id = cfg_result.data["id"]
    rows = [{"config_id": config_id, "status": "queued"} for _ in range(count)]
    result = client.table("puzzle_generation_jobs").insert(rows).execute()
    job_ids = [r["id"] for r in (result.data or [])]

    logger.info(
        "Admin queued %d generation job(s) for config '%s'",
        len(job_ids), config_name,
    )

    return create_response(
        data={"job_ids": job_ids, "count": len(job_ids), "config_name": config_name},
        status_code=201,
    )


@admin_bp.route("/puzzles/rejected", methods=["GET"])
def list_rejected_puzzles():
    """
    List rejected puzzles with their content and validation data.

    Query params:
        config_name: str  optional — defaults to "classic"
        limit:       int  optional — max results, defaults to 50

    Response (200):
        {
            "data": {
                "puzzles": [
                    {
                        "puzzle_id":         str,
                        "validation_score":  float | null,
                        "auto_fail_reasons": [str, ...],
                        "warnings":          [str, ...],
                        "created_at":        str,
                        "groups": [
                            {"relationship": str, "words": [str, str, str, str]},
                            ...
                        ]
                    },
                    ...
                ],
                "count": int
            }
        }
    """
    config_name = request.args.get("config_name", "classic")
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return create_response(error="'limit' must be an integer", status_code=400)

    from ...services.puzzle_pool_service import get_rejected_puzzles

    try:
        puzzles = get_rejected_puzzles(config_name=config_name, limit=limit)
    except ValueError as e:
        return create_response(error=str(e), status_code=404)

    return create_response(data={"puzzles": puzzles, "count": len(puzzles)})


@admin_bp.route("/puzzles/<puzzle_id>/start-review-game", methods=["POST"])
def start_review_game(puzzle_id: str):
    """
    Create a playable game session from any puzzle, regardless of status.

    Lets you play through a rejected puzzle to judge its quality yourself
    before deciding whether to approve it.

    Request body: empty (or omit entirely)

    Response (201):
        {
            "data": {
                "game_id":   str,
                "puzzle_id": str,
                "grid":      [str, ...],   # 16 shuffled words
                "connections": [...]
            }
        }
    """
    import random
    from ...services.puzzle_pool_service import _fetch_puzzle_connections
    from ...services.game_session_service import add_new_game, get_game_from_db

    try:
        connections = _fetch_puzzle_connections(puzzle_id)
    except ValueError as e:
        return create_response(error=str(e), status_code=404)

    grid = [word for c in connections for word in c["words"]]
    random.shuffle(grid)

    game_id = add_new_game(grid, connections, puzzle_id=puzzle_id)
    game_state = get_game_from_db(game_id)

    logger.info("Started review game %s for puzzle %s", game_id, puzzle_id)

    return create_response(
        data={"game_id": game_id, "puzzle_id": puzzle_id, **game_state},
        status_code=201,
    )


@admin_bp.route("/puzzles/<puzzle_id>/approve", methods=["POST"])
def manually_approve_puzzle(puzzle_id: str):
    """
    Human-override: approve a puzzle that the validation pipeline rejected.

    This does not re-run validation — it unconditionally transitions the puzzle
    to 'approved', making it eligible to be served to players. The existing
    validation_score and validation_report are preserved for audit purposes.

    Response (200):
        {
            "data": {"puzzle_id": str, "status": "approved"}
        }
    """
    from ...services.puzzle_pool_service import manually_approve_puzzle as _approve

    try:
        _approve(puzzle_id)
    except Exception as e:
        logger.error("Failed to manually approve puzzle %s: %s", puzzle_id, e)
        return create_response(error=str(e), status_code=500)

    logger.info("Admin manually approved puzzle %s", puzzle_id)
    return create_response(data={"puzzle_id": puzzle_id, "status": "approved"})
