"""CV inference service (ONNX Runtime, CPU).

- Loads an ONNX model at startup (warm-up) so the first real request
  does not pay the model-loading cost.
- Exposes GET /health (reports model status) and POST /predict.
"""

from __future__ import annotations

import os
import time
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from onnxruntime import InferenceSession

MODEL_PATH = os.getenv("MODEL_PATH", "/app/model.onnx")
# Expected input tensor shape, e.g. "1,4" -> [[0.1,0.2,0.3,0.4]]
INPUT_SHAPE = tuple(int(x) for x in os.getenv("INPUT_SHAPE", "1,4").split(","))

app = FastAPI(title="CV Inference Service", version="1.0.0")

_state: dict[str, Any] = {
    "session": None,
    "input_name": None,
    "loaded_at": None,
    "warmup_ms": None,
    "error": None,
}


class PredictRequest(BaseModel):
    # Flat list of floats; length must match product of INPUT_SHAPE.
    data: list[float] = Field(..., examples=[[0.1, 0.2, 0.3, 0.4]])


class PredictResponse(BaseModel):
    output: list[float]
    elapsed_ms: float


def _load_model() -> None:
    start = time.perf_counter()
    try:
        sess = InferenceSession(
            MODEL_PATH, providers=["CPUExecutionProvider"]
        )
        input_name = sess.get_inputs()[0].name
        # Warm-up inference with a dummy zero tensor.
        dummy = np.zeros(INPUT_SHAPE, dtype=np.float32)
        sess.run(None, {input_name: dummy})
        _state["session"] = sess
        _state["input_name"] = input_name
        _state["loaded_at"] = time.time()
        _state["warmup_ms"] = round((time.perf_counter() - start) * 1000, 2)
        _state["error"] = None
    except Exception as exc:  # noqa: BLE001
        _state["error"] = str(exc)
        raise


@app.on_event("startup")
def _startup() -> None:
    _load_model()


@app.get("/health")
def health() -> dict[str, Any]:
    loaded = _state["session"] is not None
    return {
        "status": "healthy" if loaded else "unhealthy",
        "model_loaded": loaded,
        "model_path": MODEL_PATH,
        "loaded_at": _state["loaded_at"],
        "warmup_ms": _state["warmup_ms"],
        "error": _state["error"],
    }


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    sess: InferenceSession | None = _state["session"]
    input_name: str | None = _state["input_name"]
    if sess is None or input_name is None:
        raise HTTPException(status_code=503, detail="model not loaded")

    expected = int(np.prod(INPUT_SHAPE))
    if len(req.data) != expected:
        raise HTTPException(
            status_code=422,
            detail=f"expected {expected} floats for shape {INPUT_SHAPE}, got {len(req.data)}",
        )

    arr = np.array(req.data, dtype=np.float32).reshape(INPUT_SHAPE)
    start = time.perf_counter()
    outputs = sess.run(None, {input_name: arr})
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)

    out = np.asarray(outputs[0]).reshape(-1).tolist()
    return PredictResponse(output=out, elapsed_ms=elapsed_ms)