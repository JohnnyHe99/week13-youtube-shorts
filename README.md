# 가로 영상을 쇼츠로

성균관대학교 FTM5108-01 · Week 13. 가로 영상의 움직임을 분석하고 세로 프레임을 골라, 한 편의 YouTube Shorts를 만드는 실습입니다.

## 제작 과정

| 단계 | 입력 | 출력 |
| --- | --- | --- |
| 소재 분석 | 로컬 가로 영상 | 해상도·프레임률·길이, 프레임 간 움직임, 추천 구간 및 크롭 위치 |
| 편집 설계 | 분석 결과, 5개 장면의 자막·내레이션 | 내레이션 길이에 맞춘 `edit.json`, 자막 `captions.srt` |
| 렌더링 | 편집 계획, 원본 프레임, 음성 | 9:16 H.264/AAC MP4와 JPG 썸네일 |
| 검수 | 실제 영상·썸네일과 편집 계획 | 규격·디코딩·무음 구간 측정 결과 `qa.json` |

`.claude/agents/`에는 입력 검토, 구성 검토, 출력 검수를 담당하는 프로젝트 서브에이전트가 있습니다. Claude Code에서 이 폴더를 열고 제작을 요청하면 `CLAUDE.md`의 진행 순서를 사용할 수 있습니다. 아래 Python 명령은 모델 연결 없이 로컬 미디어 도구만 사용합니다.

## 실행

Python 3.10 이상, Pillow, FFmpeg/ffprobe가 필요합니다. 기본 데모 내레이션은 macOS `say`의 Yuna 음성을 사용합니다. 사용 가능한 음성은 `say -v '?'`로 확인할 수 있습니다.

```sh
python3 -m pip install -r requirements.txt
python3 -m shorts_pipeline --demo --output dist
python3 -m shorts_pipeline --source my-horizontal-video.mp4 --brief brief.json --output my-short
```

`--output`은 아직 없는 폴더를 지정합니다. 필요하면 `--ffmpeg`와 `--ffprobe`로 도구 경로를 지정합니다.

자기 대본을 쓰려면 `brief.json`의 `beats` 배열에 도입, 소재 분석, 편집 설계, 렌더링, 검수 순으로 5개 항목을 전달합니다. 각 항목에는 `caption`과 `narration`을 넣고 자막은 2줄 이내로 작성합니다. 직접 녹음한 경우 항목에 `audio`를 추가하여 브리프 파일 기준 상대 경로를 넣을 수 있습니다. 입력 영상의 음성을 자동 전사하는 기능은 포함하지 않습니다.

## 작업 결과

- [시연 MP4](demo/short.mp4) 및 [썸네일](demo/thumbnail.jpg)
- [직접 생성한 가로 원본](demo/original.mp4)
- [편집 계획](demo/edit.json), [자막](demo/captions.srt), [기술 검수 보고서](demo/qa.json)

시연 영상은 1080×1920, 24fps입니다. 제작 도중 외부 영상과 음악을 다운로드하지 않았습니다. QA 보고서에는 디코딩, 코덱, 재생 길이, 무음 검사가 포함됩니다. 발음, 억양, 장면별 자막의 의미는 시청자가 직접 확인합니다.

## 개인 포트폴리오

로컬 작품집에서 `/#coursework/week13`로 접근할 수 있습니다. 영상과 썸네일은 `public/coursework/week13/`에 배치합니다.

## 자료

- [Week 13 Canvas 과제 공지](https://canvas.skku.edu/courses/80378/discussion_topics/663178)
- [영상 편집 및 최종 검수 안내](https://incredible-rifle-a41.notion.site/Week3-ClaudeCode-4cca16a06d274faca941eebd2f9668e1)
- [Claude Code 프로젝트 서브에이전트 문서](https://code.claude.com/docs/en/sub-agents)
