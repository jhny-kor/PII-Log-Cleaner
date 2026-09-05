# PII Log Cleaner

로그·텍스트·Office 문서 파일을 분석한 뒤 원본과 분리된 비식별화 결과를 만드는 오프라인 Windows 데스크톱 프로그램입니다.

## 라이선스

PII Log Cleaner의 자체 작성 소스 코드와 문서는 [Apache License 2.0](LICENSE) (`Apache-2.0`)으로 배포합니다. 다만 `resources/icons/flaticon/`, Python 의존성, 번들 모델은 각각 별도 라이선스가 적용되며 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)를 함께 확인해야 합니다.

## 화면 예시

![PII Log Cleaner 화면](artifacts/ui-sample-flaticon-1536x1024.png)

파일 선택, 탐지 항목, 실행 요약, 비식별화 미리보기를 포함한 이전 버전의 데모 화면입니다. v1.1.0에서는 조직명 탐지에 사용하던 ‘기타 식별정보’ 항목이 제외됩니다.

## 주요 기능

- 제공된 화면 구성을 반영한 PySide6 단일 화면 UI: 파일/폴더 선택·드래그앤드롭 추가, 10개 탐지 항목, 치환 방식, 실행 요약, 이력, 3열 미리보기
- 입력 파일: `.log`, `.txt`, `.out`, `.csv`, `.sql`, `.xls`, `.xlsx`, `.docx`, `.doc`, `.hwp`, `.hwpx`
- 주민등록번호 형식, 국내 전화번호, 이메일, IPv4, URL, 날짜, 계좌번호 문맥값, API 키/비밀번호 문맥값의 정규식 탐지
- 위치 기반 중첩 해결과 치환으로 원문 일부가 잘못 바뀌지 않도록 처리
- 로컬 `schift-ko-pii-v7` 모델 어댑터: 실행 전에 `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`을 설정하며 실행 중 모델을 내려받지 않음
- `.docx`, `.xlsx`, `.hwpx` 문서의 XML 텍스트를 구조를 유지한 `_deid` 파일로 저장
- 한 번의 스트리밍 처리로 분석·미리보기·별도 `_deid` 출력, 선택적 원본 백업, CSV 집계 보고서, PII를 저장하지 않는 로컬 SQLite 실행 이력

`.doc`, `.xls`, `.hwp` 구형 바이너리 문서는 대상 목록에는 포함되지만, 원본 형식으로 안전하게 다시 저장하려면 해당 문서 편집기 또는 별도 변환기 연동이 필요합니다.

## v1.1.0 모델 변경

- `schift-ko-pii==0.6.0`과 `transformers==5.15.0`으로 `schift-ko-pii-v7`을 실행합니다.
- v7은 약 4천만 파라미터의 모델이며 이름·주소별 독립 상위층을 사용합니다. 모델 탐지는 **이름과 주소만** 담당합니다. 모델이 반환한 이름에는 기존 앱의 한국어 이름 필터(3~4자, 성씨 및 제외어 검사)를 적용합니다.
- v7에는 조직명 탐지 헤드가 없습니다. 기존 ‘기타 식별정보’ 선택 항목을 제거했습니다. 날짜·전화번호·주민등록번호·이메일·IP·URL·계좌번호·비밀값의 정규식 처리는 유지합니다. 앱의 ‘날짜’는 생년월일에 한정되지 않는 기존 날짜 형식 탐지입니다.
- `detect(postprocess=False, normalize=False, extended=False)`로 원문 위치를 유지하고 앱의 정규식·중첩 해결·마스킹을 사용합니다. 모델 패키지의 위험도별 선택적 마스킹은 사용하지 않으며, 선택한 항목의 탐지 결과를 기존 방식으로 치환합니다.
- 번들 스냅샷은 [리비전 `9d9bc145c57371fd5fd70575b47f37af47a39728`](https://huggingface.co/schift-io/schift-ko-pii-v7/tree/9d9bc145c57371fd5fd70575b47f37af47a39728)으로 고정했습니다. 가중치 SHA-256은 `b1b9a6f82e22cbaeebba882f1f8236161c0af8e3ae5baac07511955c32679f81`입니다.

## 모델도 설치파일에 포함되나요?

네. **저장소에 포함된 로컬 모델 스냅샷은 최종 `PII-Log-Cleaner-Setup.exe` 안에 포함됩니다.**

모델 원본 파일은 Git 호스팅의 파일당 크기 제한을 넘지 않도록 저장소 안에서 50MB 조각으로 관리합니다. 빌드 스크립트가 SHA-256을 확인해 원본 `model.safetensors`를 자동 복원한 후, PyInstaller의 `--add-data`로 `models\schift-ko-pii-v7` 경로에 복사합니다. 이후 Inno Setup이 PyInstaller 결과 폴더 전체를 하나의 설치파일로 묶습니다. 설치된 프로그램은 번들 모델만 읽으며 인터넷에서 모델을 받지 않습니다.

모델 가중치와 원본 `LICENSE` 파일도 저장소에 포함합니다. 모델과 런타임이 함께 들어가므로 설치파일 크기는 커집니다.

필수 파일은 `config.json`, `tokenizer.json`, `tokenizer_config.json`, `modeling_lfm2_bidirectional.py`, `schift_heads.json`, `model.safetensors`입니다. `schift_heads.json`은 v7의 이름·주소 모델 구성을 지정합니다. 프로그램은 이 로컬 폴더만 로드하며, 파일이 없거나 모델 초기화에 실패하면 일반 실행을 중단합니다. v6으로 자동 전환하지 않습니다.

## 모델 라이선스와 배포 조건

모델 원문과 스냅샷 정보는 [Hugging Face의 `schift-io/schift-ko-pii-v7` 저장소](https://huggingface.co/schift-io/schift-ko-pii-v7)에서 확인할 수 있습니다.

`schift-io/schift-ko-pii-v7` 모델은 **Apache-2.0이 아닌 [Schift License v2.0](https://huggingface.co/schift-io/schift-ko-pii-v7/blob/main/LICENSE)**으로 배포됩니다. 이 라이선스는 Apache License 2.0을 기반으로 하지만, 최근 완료 회계연도 기준 연 매출이 미화 1,000만 달러를 초과하는 법인의 상업적 사용에는 별도 상용 라이선스를 요구하는 추가 조건이 있습니다. 연구·교육·평가·개인 프로젝트·비영리 단체 사용은 매출과 무관하게 허용된다고 모델 라이선스에 명시되어 있습니다.

따라서 이 저장소의 `Apache-2.0` 표기는 PII Log Cleaner의 자체 작성 코드·문서에만 적용되며, 모델 가중치·모델 코드에는 적용되지 않습니다. Windows 설치파일을 배포할 때는 모델 스냅샷에 포함된 원본 `LICENSE*` 파일을 변경하지 않고 함께 포함해야 합니다. 빌드 스크립트가 이를 확인하며, 상세 고지는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 제공합니다. 모델 라이선스는 배포 전 해당 스냅샷의 원문으로 다시 확인하세요.

## Windows에서 단일 설치파일 만들기

빌드 머신 준비물:

1. 64비트 Python 3.11 권장(3.10 이상 지원)과 Inno Setup 6

PowerShell에서 실행합니다.

```powershell
.\build-windows.ps1
```

완료되면 `dist\PII-Log-Cleaner-Setup.exe` 한 개가 만들어집니다. 내부적으로는 PyInstaller `onedir` 구조를 사용해 모델을 설치 폴더에 정상 배치한 뒤, Inno Setup이 이를 단일 설치파일로 만듭니다.

빌드 스크립트는 `py -3`이 실패해도 PATH의 `python`, `python.exe`, `python3`을 차례로 확인해 현재 설치된 64비트 Python 3.10 이상을 선택합니다. 여러 런타임이 있거나 자동 탐지가 실패하면 다음처럼 현재 `python -V`에서 보이는 실행 파일만 직접 지정할 수 있습니다.

```powershell
$pythonExe = (Get-Command python -CommandType Application).Path
.\build-windows.ps1 -PythonExe $pythonExe
```

`python -V`가 정상 출력되는데도 빌드가 실패했다면 위의 `-PythonExe` 방식으로 실행합니다. 모델 경로는 묻지 않으며, 누락되거나 변조된 모델 조각은 SHA-256 검증 단계에서 중단됩니다.

## 브랜딩 자산

사용자가 제공한 방패·문서·빗자루 이미지를 앱 창 아이콘, Windows 실행 파일·설치 마법사 아이콘으로 사용합니다. 워드마크 이미지는 제목 표시줄에 사용하며, 기능 버튼의 보조 아이콘은 기존 Flaticon 자산을 유지합니다.

## 로컬 검사

```bash
python3 -m unittest discover -s tests -v
```

실제 모델까지 검사하려면 의존성을 설치하고 가중치 조각을 복원한 환경에서 실행합니다. 아래 검사는 빈 Hugging Face 캐시와 네트워크 연결 차단 상태에서 v7 추론, 긴 입력의 위치, 텍스트·문서 비식별화와 원본 보존을 확인합니다.

```bash
PII_RUN_MODEL_SMOKE=1 python3 -m unittest discover -s tests -v
```

Windows PowerShell에서는 `$env:PII_RUN_MODEL_SMOKE = "1"` 설정 후 `python -m unittest discover -s tests -v`로 실행합니다. PowerShell 7(`pwsh`)이 있으면 빌드 스크립트의 가중치 복원·손상 검증도 실행합니다.

2026-09-06 macOS / Python 3.11 검증: 실제 v7 오프라인 추론을 포함한 23개 검사 통과, PowerShell의 실제 4개 모델 조각 복원 및 SHA-256 검증 통과. 텍스트·문서는 합성 테스트 자료로 검사했습니다. Windows 설치파일 생성·설치 확인은 미실시이며 Windows에서 별도로 수행해야 합니다.

`--demo`, `--allow-regex-only`는 번들 모델 없이 UI를 확인하기 위한 개발 전용 옵션이며 Windows 설치 경로에서는 사용하지 않습니다.
