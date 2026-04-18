from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request
from sqlalchemy.orm import Session

from leadflow import repositories
from leadflow.config import get_settings
from leadflow.db.migrate import run_migrations
from leadflow.db.session import SessionLocal, configure_session
from leadflow.schemas import PromptCreateRequest
from leadflow.services.workflow import build_context, place_prospect_call, serialize_prompt, serialize_prompt_prospect

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_db() -> Session:
    if SessionLocal.kw.get("bind") is None:
        configure_session(get_settings().database_url)
    return SessionLocal()


def _json_error(status_code: int, message: str):
    response = jsonify({"detail": message})
    response.status_code = status_code
    return response


def create_app() -> Flask:
    settings = get_settings()
    configure_session(settings.database_url)

    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
        static_url_path="/static",
    )
    app.config["JSON_SORT_KEYS"] = False
    app.config["APP_NAME"] = settings.app_name

    run_migrations()

    @app.errorhandler(404)
    def handle_404(_: Exception):
        if request.path.startswith("/api/"):
            return _json_error(404, "Not found")
        return ("Not found", 404)

    @app.errorhandler(400)
    def handle_400(exc: Exception):
        if request.path.startswith("/api/"):
            return _json_error(400, str(exc))
        return (str(exc), 400)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/")
    def index():
        db = _get_db()
        try:
            prompts = repositories.list_prompts(db, limit=12)
            selected_prompt_id = prompts[0].id if prompts else None
            return render_template(
                "index.html",
                app_name=settings.app_name,
                selected_prompt_id=selected_prompt_id,
                recent_prompts=[serialize_prompt(prompt) for prompt in prompts],
            )
        finally:
            db.close()

    @app.get("/prompts/<prompt_id>")
    def prompt_detail(prompt_id: str):
        db = _get_db()
        try:
            prompt = repositories.get_prompt(db, prompt_id)
            if not prompt:
                abort(404)
            prompts = repositories.list_prompts(db, limit=12)
            return render_template(
                "index.html",
                app_name=settings.app_name,
                selected_prompt_id=prompt_id,
                recent_prompts=[serialize_prompt(item) for item in prompts],
            )
        finally:
            db.close()

    @app.post("/api/prompts")
    def create_prompt():
        payload = PromptCreateRequest.model_validate(request.get_json(force=True, silent=False) or {})
        db = _get_db()
        try:
            prompt = repositories.create_prompt(db, payload.prompt, payload.requested_limit)
            return jsonify(serialize_prompt(prompt))
        finally:
            db.close()

    @app.get("/api/prompts")
    def list_prompts():
        db = _get_db()
        try:
            items = [serialize_prompt(item) for item in repositories.list_prompts(db, limit=20)]
            return jsonify({"items": items})
        finally:
            db.close()

    @app.get("/api/prompts/<prompt_id>")
    def get_prompt(prompt_id: str):
        db = _get_db()
        try:
            prompt = repositories.get_prompt(db, prompt_id)
            if not prompt:
                return _json_error(404, "Prompt not found")
            return jsonify(serialize_prompt(prompt))
        finally:
            db.close()

    @app.get("/api/prompts/<prompt_id>/prospects")
    def list_prompt_prospects(prompt_id: str):
        db = _get_db()
        try:
            prompt = repositories.get_prompt(db, prompt_id)
            if not prompt:
                return _json_error(404, "Prompt not found")
            items = [serialize_prompt_prospect(item) for item in repositories.list_prompt_prospects(db, prompt_id)]
            return jsonify({"items": items})
        finally:
            db.close()

    @app.post("/api/prompts/<prompt_id>/retry")
    def retry_prompt(prompt_id: str):
        db = _get_db()
        try:
            prompt = repositories.get_prompt(db, prompt_id)
            if not prompt:
                return _json_error(404, "Prompt not found")
            prompt = repositories.reset_prompt_for_retry(db, prompt)
            return jsonify(serialize_prompt(prompt))
        finally:
            db.close()

    @app.post("/api/prompt-prospects/<prompt_prospect_id>/call")
    def call_prompt_prospect(prompt_prospect_id: str):
        db = _get_db()
        try:
            item = repositories.get_prompt_prospect(db, prompt_prospect_id)
            if not item:
                return _json_error(404, "Prospect not found")
            workflow = build_context(settings)
            response = place_prospect_call(db, item, workflow)
            return jsonify(
                {
                    "prompt_prospect_id": item.id,
                    "voicecall_call_id": response["call_id"],
                    "status": response["status"],
                }
            )
        finally:
            db.close()

    return app
