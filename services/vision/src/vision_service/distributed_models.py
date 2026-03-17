from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class NodeRegistrationBody(BaseModel):
    name: str
    sshAlias: str | None = None
    hostname: str
    gpuAvailable: bool = False
    gpuName: str | None = None
    dockerVersion: str | None = None
    nvidiaRuntimeVersion: str | None = None


class WorkerRegistrationBody(BaseModel):
    workerName: str
    queueNames: list[str] = Field(default_factory=list)
    capacitySlots: int = 1
    supportsFace: bool = False
    supportsTextEmbedding: bool = False
    supportsImageEmbedding: bool = False
    supportsGpu: bool = False
    detectorModel: str | None = None
    embeddingModel: str | None = None
    faceModel: str | None = None


class WorkerRegistrationEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workerId: str
    node: NodeRegistrationBody
    worker: WorkerRegistrationBody


class WorkerHeartbeatRuntime(BaseModel):
    cpuPercent: float | None = None
    memoryPercent: float | None = None
    gpuPercent: float | None = None
    gpuMemoryPercent: float | None = None


class WorkerHeartbeatEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workerId: str
    status: str
    activeJobs: int = 0
    queueDepthHint: int = 0
    runtime: WorkerHeartbeatRuntime = Field(default_factory=WorkerHeartbeatRuntime)
    checkedAt: str


class JobStatusEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workerId: str | None = None
    attemptNo: int = 1
    status: str
    detail: str | None = None
    durationSec: float | None = None
    metrics: dict[str, int | float | str | None] = Field(default_factory=dict)


class TrackArtifactBody(BaseModel):
    role: str
    kind: str
    mimeType: str = "image/jpeg"
    payloadBase64: str


class TrackBundleBody(BaseModel):
    trackRow: dict[str, object]
    artifacts: list[TrackArtifactBody] = Field(default_factory=list)
    embedding: dict[str, object]
    faceEmbedding: dict[str, object] | None = None


class JobResultsEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workerId: str
    durationSec: float
    trackBundles: list[TrackBundleBody] = Field(default_factory=list)
