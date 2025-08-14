import io
import os
import time
from http import HTTPStatus

import numpy as np
import ormsgpack
import soundfile as sf
import torch
from kui.asgi import (
    Body,
    HTTPException,
    HttpView,
    JSONResponse,
    Routes,
    StreamResponse,
    request,
)
from loguru import logger
from typing_extensions import Annotated

from fish_speech.utils.schema import (
    OpenAITTSRequest,
    ServeTTSRequest,
    ServeVQGANDecodeRequest,
    ServeVQGANDecodeResponse,
    ServeVQGANEncodeRequest,
    ServeVQGANEncodeResponse,
)
from tools.server.api_utils import (
    buffer_to_async_generator,
    get_content_type,
    inference_async,
)
from tools.server.inference import inference_wrapper as inference
from tools.server.model_manager import ModelManager
from tools.server.model_utils import (
    batch_vqgan_decode,
    cached_vqgan_batch_encode,
)

MAX_NUM_SAMPLES = int(os.getenv("NUM_SAMPLES", 1))

routes = Routes()


@routes.http("/v1/health")
class Health(HttpView):
    @classmethod
    async def get(cls):
        return JSONResponse({"status": "ok"})

    @classmethod
    async def post(cls):
        return JSONResponse({"status": "ok"})


@routes.http.post("/v1/vqgan/encode")
async def vqgan_encode(req: Annotated[ServeVQGANEncodeRequest, Body(exclusive=True)]):
    # Get the model from the app
    model_manager: ModelManager = request.app.state.model_manager
    decoder_model = model_manager.decoder_model

    # Encode the audio
    start_time = time.time()
    tokens = cached_vqgan_batch_encode(decoder_model, req.audios)
    logger.info(f"[EXEC] VQGAN encode time: {(time.time() - start_time) * 1000:.2f}ms")

    # Return the response
    return ormsgpack.packb(
        ServeVQGANEncodeResponse(tokens=[i.tolist() for i in tokens]),
        option=ormsgpack.OPT_SERIALIZE_PYDANTIC,
    )


@routes.http.post("/v1/vqgan/decode")
async def vqgan_decode(req: Annotated[ServeVQGANDecodeRequest, Body(exclusive=True)]):
    # Get the model from the app
    model_manager: ModelManager = request.app.state.model_manager
    decoder_model = model_manager.decoder_model

    # Decode the audio
    tokens = [torch.tensor(token, dtype=torch.int) for token in req.tokens]
    start_time = time.time()
    audios = batch_vqgan_decode(decoder_model, tokens)
    logger.info(f"[EXEC] VQGAN decode time: {(time.time() - start_time) * 1000:.2f}ms")
    audios = [audio.astype(np.float16).tobytes() for audio in audios]

    # Return the response
    return ormsgpack.packb(
        ServeVQGANDecodeResponse(audios=audios),
        option=ormsgpack.OPT_SERIALIZE_PYDANTIC,
    )


@routes.http.post("/v1/tts")
async def tts(req: Annotated[ServeTTSRequest, Body(exclusive=True)]):
    # Get the model from the app
    app_state = request.app.state
    model_manager: ModelManager = app_state.model_manager
    engine = model_manager.tts_inference_engine
    sample_rate = engine.decoder_model.sample_rate

    # Check if the text is too long
    if app_state.max_text_length > 0 and len(req.text) > app_state.max_text_length:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            content=f"Text is too long, max length is {app_state.max_text_length}",
        )

    # Check if streaming is enabled
    if req.streaming and req.format != "wav":
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            content="Streaming only supports WAV format",
        )

    # Perform TTS
    if req.streaming:
        return StreamResponse(
            iterable=inference_async(req, engine),
            headers={
                "Content-Disposition": f"attachment; filename=audio.{req.format}",
            },
            content_type=get_content_type(req.format),
        )


def convert_openai_to_fish_request(openai_req: OpenAITTSRequest) -> ServeTTSRequest:
    """OpenAI TTS 요청을 Fish Speech TTS 요청으로 변환"""
    
    # response_format 매핑
    format_mapping = {
        "mp3": "mp3",
        "opus": "wav",  # Fish Speech doesn't support opus, use wav
        "aac": "wav",   # Fish Speech doesn't support aac, use wav
        "flac": "wav",  # Fish Speech doesn't support flac, use wav
        "wav": "wav",
        "pcm": "pcm",
    }
    
    audio_format = format_mapping.get(openai_req.response_format, "wav")
    
    # 모델과 음성은 무시하고 기존 Fish Speech 방식으로 랜덤 생성
    return ServeTTSRequest(
        text=openai_req.input,
        format=audio_format,
        reference_id=None,  # 랜덤 생성을 위해 None
        references=[],      # 빈 리스트로 랜덤 생성
        streaming=False,
        normalize=True,
    )


@routes.http.post("/v1/audio/speech")
async def openai_tts(req: Annotated[OpenAITTSRequest, Body(exclusive=True)]):
    """OpenAI compatible TTS API endpoint"""
    
    # OpenAI 요청을 Fish Speech 요청으로 변환
    fish_req = convert_openai_to_fish_request(req)
    
    # Get the model from the app
    app_state = request.app.state
    model_manager: ModelManager = app_state.model_manager
    engine = model_manager.tts_inference_engine
    sample_rate = engine.decoder_model.sample_rate

    # Check if the text is too long (OpenAI limit is 4096 characters)
    if len(req.input) > 4096:
        raise HTTPException(
            HTTPStatus.BAD_REQUEST,
            content="Text is too long, max length is 4096 characters",
        )

    # Perform TTS using existing Fish Speech logic
    fake_audios = next(inference(fish_req, engine))
    buffer = io.BytesIO()
    
    # speed 조절 (간단한 구현)
    if req.speed != 1.0:
        # speed가 1.0이 아닌 경우, 샘플레이트를 조절하여 속도 변경 효과
        adjusted_sample_rate = int(sample_rate * req.speed)
        sf.write(
            buffer,
            fake_audios,
            adjusted_sample_rate,
            format=fish_req.format,
        )
    else:
        sf.write(
            buffer,
            fake_audios,
            sample_rate,
            format=fish_req.format,
        )

    # OpenAI API는 바이너리 오디오 데이터를 직접 반환
    return StreamResponse(
        iterable=buffer_to_async_generator(buffer.getvalue()),
        content_type=get_content_type(fish_req.format),
    )
