from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/healthcheck")
async def healthcheck(request: Request):
    return request.app.state
