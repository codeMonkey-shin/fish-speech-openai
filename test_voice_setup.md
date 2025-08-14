# Voice 설정 가이드

## 1. 레퍼런스 음성 파일 준비

**권장 방식 (직접 파일):**
```
references/
├── test1.mp3
├── test1.lab
├── speaker2.wav
├── speaker2.lab
└── korean_voice.flac
```

**기존 방식 (폴더, 하위 호환성):**
```
references/
├── test1/
│   ├── sample1.wav
│   ├── sample1.lab
│   ├── sample2.wav
│   └── sample2.lab
└── speaker2/
    ├── voice1.mp3
    └── voice1.lab
```

## 2. .lab 파일 내용 예시

```
# test1.lab
안녕하세요, 저는 테스트 화자입니다.

# speaker2.lab
이것은 두 번째 샘플 음성입니다.
```

## 3. API 사용법

### OpenAI 호환 API 사용
```bash
curl -X POST "http://localhost:8080/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tts-1",
    "input": "안녕하세요, 테스트 음성입니다.",
    "voice": "test1",
    "response_format": "mp3"
  }'
```

### Fish Speech 네이티브 API 사용
```bash
curl -X POST "http://localhost:8080/v1/tts" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "안녕하세요, 테스트 음성입니다.",
    "reference_id": "test1",
    "format": "wav"
  }'
```

## 4. 동작 방식

- OpenAI API의 `voice: "test1"` → Fish Speech의 `reference_id: "test1"`로 변환
- **우선순위 1**: `references/test1.mp3` (또는 .wav, .flac 등) 직접 파일 사용
- **우선순위 2**: `references/test1/` 폴더의 모든 오디오 파일 사용 (하위 호환성)
- 같은 이름의 `.lab` 파일이 있으면 텍스트 프롬프트로 함께 사용

## 5. 파일 우선순위

시스템은 다음 순서로 파일을 찾습니다:
1. `references/test1.mp3`
2. `references/test1.wav`
3. `references/test1.flac`
4. ... (기타 지원 확장자)
5. `references/test1/` 폴더 내 파일들 (폴백)