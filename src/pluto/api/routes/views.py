"""HTML view routes serving Studio pages."""

from fastapi import APIRouter
from fastapi.responses import FileResponse
from src.pluto.core.config import get_settings

router = APIRouter(tags=["views"])


@router.get("/")
def read_root():
    settings = get_settings()
    onboarding_file = settings.web_dir / "onboarding.html"
    if onboarding_file.exists():
        return FileResponse(onboarding_file)
    return FileResponse(settings.web_dir / "index.html")


@router.get("/onboarding")
def read_onboarding():
    settings = get_settings()
    return FileResponse(settings.web_dir / "onboarding.html")


@router.get("/create")
def read_create():
    settings = get_settings()
    return FileResponse(settings.web_dir / "create.html")


@router.get("/studio")
@router.get("/editor")
def read_studio():
    settings = get_settings()
    return FileResponse(settings.web_dir / "index.html")


@router.get("/cockpit")
@router.get("/settings")
def read_cockpit():
    settings = get_settings()
    cockpit_file = settings.web_dir / "cockpit.html"
    if cockpit_file.exists():
        return FileResponse(cockpit_file)
    return FileResponse(settings.web_dir / "index.html")


@router.get("/docs")
@router.get("/documentation")
def read_docs():
    settings = get_settings()
    docs_file = settings.web_dir / "docs.html"
    if docs_file.exists():
        return FileResponse(docs_file)
    return FileResponse(settings.web_dir / "index.html")


@router.get("/oven")
def read_oven():
    settings = get_settings()
    oven_file = settings.web_dir / "oven.html"
    if oven_file.exists():
        return FileResponse(oven_file)
    return FileResponse(settings.web_dir / "index.html")


@router.get("/blueprint")
def read_blueprint():
    settings = get_settings()
    blueprint_file = settings.web_dir / "blueprint.html"
    if blueprint_file.exists():
        return FileResponse(blueprint_file)
    return FileResponse(settings.web_dir / "index.html")
