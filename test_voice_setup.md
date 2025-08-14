# Voice 설정 가이드

## 1. 레퍼런스 음성 파일 준비

다음과 같은 구조로 파일을 준비하세요:

```
references/
├── test1/
│   ├── sample1.wav
│   ├── sample1.lab
│   ├── sample2.wav
│   └── sample2.lab
└── speaker2/
    ├── voice1.mp3
    ├── voice1.lab
    ├── voice2.mp3
    └── voice2.lab
```

## 2. .lab 파일 내용 예시

```
# sample1.lab
안녕하세요, 저는 테스트 화자입니다.

# sample2.lab  
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
- `references/test1/` 폴더의 모든 오디오 파일을 레퍼런스로 사용
- 같은 이름의 `.lab` 파일이 있으면 텍스트 프롬프트로 함께 사용