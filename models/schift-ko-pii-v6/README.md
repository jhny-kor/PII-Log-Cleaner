# 번들 모델

이 폴더에는 `schift-io/schift-ko-pii-v6`의 빌드용 스냅샷이 포함됩니다. Git 호스팅의 파일당 크기 제한을 넘지 않도록 `model.safetensors`는 `model.safetensors.part-000`부터 분할해 저장합니다. `build-windows.ps1`이 SHA-256을 검증한 뒤 원본 파일로 자동 복원하므로, 별도 다운로드나 `-ModelPath` 지정은 필요하지 않습니다.

원본 모델: [Hugging Face 모델 페이지](https://huggingface.co/schift-io/schift-ko-pii-v6), 검증한 리비전: `f3c1807255360e8adaa04e7284619a5b433320fa`.

## 모델 라이선스

이 모델은 **[Schift License v2.0](https://huggingface.co/schift-io/schift-ko-pii-v6/blob/main/LICENSE)**으로 배포되며, PII Log Cleaner 자체 코드의 Apache-2.0 라이선스와 별개입니다. Apache License 2.0 기반이지만, 최근 완료 회계연도 기준 연 매출이 미화 1,000만 달러를 초과하는 법인의 상업적 사용에는 별도 상용 라이선스가 필요합니다. 연구·교육·평가·개인 프로젝트·비영리 단체 사용은 매출과 관계없이 허용된다고 원문에 명시되어 있습니다.

빌드에 사용하는 스냅샷의 원본 `LICENSE` 파일을 변경하지 말고, 모델 가중치와 함께 보관·배포하세요. 라이선스 조건은 배포 시점에 해당 스냅샷의 원문으로 다시 확인해야 합니다.

## 빌드 입력

빌드 스크립트는 `config.json`, `tokenizer.json`, `tokenizer_config.json`, 복원된 `model.safetensors`, `modeling_lfm2_bidirectional.py`, 모델 라이선스 파일(`LICENSE*`)을 요구합니다. 이 파일들은 빌드 시 설치파일에 포함되며, 실행 프로그램은 해당 로컬 경로만 읽고 Hugging Face에서 내려받지 않습니다.
