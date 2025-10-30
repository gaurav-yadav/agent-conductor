from importlib import resources

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

from agent_conductor.services.session_service import SessionService
from agent_conductor.services.inbox_service import InboxService
from agent_conductor.services.approval_service import ApprovalService
from agent_conductor.models.enums import ApprovalStatus
from agent_conductor.utils import agent_profiles


def _templates() -> Jinja2Templates:
    template_dir = resources.files("agent_conductor.ui") / "templates"
    return Jinja2Templates(directory=str(template_dir))


def create_router(
    session_service: SessionService,
    inbox_service: InboxService,
    approval_service: ApprovalService,
) -> APIRouter:
    router = APIRouter()
    templates = _templates()

    @router.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request):
        sessions = session_service.list_sessions()
        approvals = approval_service.list_requests(status=ApprovalStatus.PENDING)
        inbox_summary = {
            terminal.id: inbox_service.list_messages(terminal.id)
            for session in sessions
            for terminal in session.terminals
            if terminal.window_name.startswith("supervisor-")
        }
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "sessions": sessions,
                "approvals": approvals,
                "inbox_summary": inbox_summary,
                "bundled_personas": agent_profiles.bundled_profile_names(),
            },
        )

    return router
