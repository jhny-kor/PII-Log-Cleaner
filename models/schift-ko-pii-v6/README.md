# 번들 모델 입력

Windows 빌드 전 이 폴더 또는 `-ModelPath`로 지정한 폴더에 라이선스가 포함된 `schift-io/schift-ko-pii-v6` 모델 스냅샷을 둡니다.

빌드 스크립트는 `config.json`, `tokenizer.json`, `tokenizer_config.json`, `model.safetensors`, `modeling_lfm2_bidirectional.py`, 모델 라이선스 파일(`LICENSE*`)을 요구합니다. 이 파일들은 빌드 시 설치파일에 포함되며, 실행 프로그램은 해당 로컬 경로만 읽고 Hugging Face에서 내려받지 않습니다.

모델 가중치와 라이선스 파일은 배포 권한·용량 문제로 GitHub 저장소에 커밋하지 마세요.
