from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/healthcheck")
async def healthcheck(request: Request):
    return {"message": "Hello World", "startup_completed": request.app.state.manager_state}
