from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import projectConfig
from app.routers import geo

app = FastAPI(
    title=projectConfig.__projname__,
    version=projectConfig.__version__,
    description=projectConfig.__description__
)

origins = ["*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(geo.router)