---
title: "Github 블로그에 익명 댓글 기능 추가 하기"
date: 2026-05-08 18:25:00 +0900
description: "GitHub Pages 블로그에 Remark42를 붙여 익명 댓글, GitHub 로그인, 관리자 삭제, Telegram 알림까지 설정한 과정"
author: dabin
categories: [Project]
tags: [github-pages, jekyll, remark42, comments, oracle-cloud, telegram]
---

이 블로그는 GitHub Pages와 Jekyll 기반으로 운영하고 있습니다.

기존에는 댓글 기능을 `utterances`로 붙여두었습니다.  
`utterances`는 GitHub Issue를 댓글 저장소처럼 사용하는 방식이라 설정이 간단하고 안정적입니다. 다만 댓글을 남기려면 GitHub 계정으로 로그인해야 한다는 점이 아쉬웠습니다.

블로그 글에 대한 간단한 질문이나 오류 제보는 로그인 없이도 남길 수 있으면 좋겠다고 생각했습니다. 그래서 이번에는 **익명 댓글이 가능한 댓글 시스템**으로 바꾸는 작업을 진행했습니다.

최종적으로 선택한 방식은 **Remark42를 Oracle Cloud 서버에 직접 배포하고, GitHub Pages 블로그에서 해당 서버를 불러오는 구조**입니다.

## 목표

이번 작업에서 원한 것은 단순히 댓글창 하나를 붙이는 것이 아니었습니다.

- 익명 댓글을 남길 수 있어야 한다.
- GitHub 로그인 댓글도 가능해야 한다.
- 댓글은 글별로 분리되어 저장되어야 한다.
- 블로그 테마와 크게 어색하지 않아야 한다.
- 부적절한 댓글은 관리자가 삭제할 수 있어야 한다.
- 새 댓글이 달리면 Telegram으로 알림을 받을 수 있어야 한다.

GitHub Pages는 정적 사이트이기 때문에 자체적으로 서버에 댓글을 저장할 수 없습니다.  
따라서 댓글을 저장하고 관리할 별도의 백엔드가 필요합니다.

## Remark42를 선택한 이유

처음에는 여러 댓글 시스템을 비교했습니다. 그중 Remark42를 선택한 이유는 아래와 같습니다.

- 익명 댓글을 지원한다.
- GitHub, Google 같은 소셜 로그인을 붙일 수 있다.
- 오픈소스라서 직접 서버에 올려 사용할 수 있다.
- 광고가 없다.
- 댓글 데이터가 내 서버에 저장된다.
- 관리자 권한으로 댓글 삭제와 차단이 가능하다.
- Telegram 알림을 지원한다.

Disqus처럼 외부 서비스에 전부 맡기는 방식보다, 내 서버에 직접 올려두는 편이 블로그의 성격과 더 잘 맞았습니다.

## 전체 구조

구조는 아래처럼 잡았습니다.

```text
사용자 브라우저
  |
  |  블로그 글 접속
  v
GitHub Pages / Jekyll 블로그
  |
  |  Remark42 embed script 로드
  v
comments.masanam.co.kr
  |
  |  Caddy reverse proxy
  v
Remark42 Docker container
  |
  |  댓글 저장
  v
BoltDB volume
```

블로그 자체는 여전히 GitHub Pages에서 정적으로 배포됩니다.  
댓글 입력창과 댓글 목록만 `comments.masanam.co.kr`에 떠 있는 Remark42 서버에서 가져오는 방식입니다.

## 1. 댓글용 도메인 준비

Remark42 서버를 블로그와 분리해서 운영하기 위해 댓글 전용 서브도메인을 만들었습니다.

```text
comments.masanam.co.kr
```

DNS에는 A 레코드를 추가했습니다.

```text
Host: comments
Type: A
Value: <Oracle Cloud 인스턴스의 공인 IP>
```

처음에는 Oracle Cloud 쪽 네트워크 설정도 같이 확인해야 했습니다.  
서버에 도메인을 연결해도, VCN 보안목록에서 80번과 443번 포트가 열려 있지 않으면 외부에서 접속할 수 없습니다.

OCI 보안목록에는 아래 수신 규칙을 추가했습니다.

```text
Source CIDR: 0.0.0.0/0
Protocol: TCP
Destination Port: 80
Description: HTTP for Remark42

Source CIDR: 0.0.0.0/0
Protocol: TCP
Destination Port: 443
Description: HTTPS for Remark42
```

여기서 `Stateless`는 선택하지 않았습니다. 기본값처럼 stateful 규칙으로 두었습니다.

Oracle Cloud 서버 자체를 만드는 과정과 SSH 접속 설정은 별도로 **Oracle 내 서버 구축하기**라는 콘텐츠로 작성하겠습니다.

## 2. Remark42와 Caddy 배포

서버에는 Docker Compose로 Remark42와 Caddy를 같이 띄웠습니다.

Caddy는 HTTPS 인증서를 자동으로 발급받고, 외부 요청을 Remark42 컨테이너로 넘겨주는 reverse proxy 역할을 합니다.

디렉터리는 아래처럼 잡았습니다.

```text
/opt/remark42
  docker-compose.yml
  Caddyfile
  .env
  var/
```

`docker-compose.yml`은 대략 이런 구조입니다.

```yaml
services:
  remark42:
    image: ghcr.io/umputun/remark42:latest
    container_name: remark42
    restart: unless-stopped
    env_file:
      - .env
    environment:
      - STORE_BOLT_PATH=/srv/var
      - BACKUP_PATH=/srv/var/backup
    volumes:
      - ./var:/srv/var

  caddy:
    image: caddy:2
    container_name: remark42-caddy
    restart: unless-stopped
    depends_on:
      - remark42
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./caddy_data:/data
      - ./caddy_config:/config
```

`Caddyfile`은 단순하게 Remark42로 프록시하도록 설정했습니다.

```caddy
comments.example.com {
  encode gzip zstd
  reverse_proxy remark42:8080
}
```

운영 중에는 Remark42의 웹 리소스 캐시 때문에 locale 수정이 바로 반영되지 않는 경우가 있어 `/web/*` 경로에 `Cache-Control`을 추가했습니다.

```caddy
comments.example.com {
  encode gzip zstd

  @remark_web path /web/*
  header @remark_web Cache-Control "no-store, no-cache, must-revalidate, max-age=0"

  reverse_proxy remark42:8080
}
```

## 3. Remark42 환경변수 설정

Remark42 설정은 `.env`에 넣었습니다.

민감한 값은 저장소에 넣으면 안 됩니다.  
특히 `SECRET`, `ADMIN_PASSWD`, GitHub OAuth secret, Telegram bot token은 반드시 서버의 `.env`에만 둡니다.

기본 설정은 아래와 같은 흐름입니다.

```bash
REMARK_URL=https://comments.example.com
SITE=masanam
SECRET=<remark42-secret>
AUTH_ANON=true
ADMIN_PASSWD=<admin-password>
TIME_ZONE=Asia/Seoul
```

여기서 중요한 값은 `SITE`입니다.  
블로그에서 넣는 `site_id`와 Remark42 서버의 `SITE` 값이 같아야 댓글이 정상적으로 연결됩니다.

익명 댓글은 아래 설정으로 켰습니다.

```bash
AUTH_ANON=true
```

이후 컨테이너를 실행했습니다.

```bash
docker compose up -d
```

상태는 아래처럼 확인했습니다.

```bash
docker compose ps
```

## 4. Jekyll 블로그에 Remark42 연결

블로그의 `_config.yml`에는 댓글 시스템을 Remark42로 바꾸었습니다.

```yaml
comments:
  active: remark42
  remark42:
    host: https://comments.masanam.co.kr
    site_id: masanam
```

그리고 `_includes/comments/remark42.html` 파일을 만들어 Remark42 embed script를 불러오도록 했습니다.

```html
<section class="remark42-comments" aria-label="댓글">
  <div class="remark42-comments__header">
    <h2>댓글</h2>
    <p>내용에 대한 오류 수정 요청, 질문은 언제나 환영입니다. 자유롭게 댓글을 남겨주세요! (하지만 부적절한 댓글은 삭제될 수 있습니다)</p>
  </div>

  <div id="remark42" class="remark42-comments__embed"></div>
</section>

<script>
  var remark_config = window.remark_config = {
    host: '{{ site.comments.remark42.host }}',
    site_id: '{{ site.comments.remark42.site_id }}',
    url: window.location.origin + window.location.pathname,
    components: ['embed'],
    theme: 'dark',
    locale: 'ko',
    no_footer: true
  };

  (function () {
    const script = document.createElement('script');
    script.src = remark_config.host + '/web/embed.js';
    script.defer = true;
    document.head.appendChild(script);
  })();
</script>
```

실제 적용 코드에서는 블로그의 dark/light mode 변경에 맞춰 Remark42 theme도 같이 바뀌도록 처리했습니다.

댓글 위치도 조정했습니다.  
처음에는 관련 글 아래에 댓글이 붙어 있었는데, 글을 읽은 사람이 바로 댓글을 남길 수 있도록 댓글을 관련 글보다 위에 배치했습니다.

`_layouts/post.html`의 tail include 순서를 아래처럼 바꾸었습니다.

```yaml
tail_includes:
  - comments
  - related-posts
  - post-nav
```

## 5. 댓글 UI 문구 다듬기

Remark42 기본 UI는 영어 또는 기본 한국어 번역을 사용합니다.  
블로그 분위기에 맞게 몇 가지 문구를 다듬었습니다.

예를 들어 아래처럼 바꾸었습니다.

```json
{
  "auth.signin": "작성자",
  "auth.submit": "설정",
  "commentForm.send": "작성"
}
```

이 작업에서 한 번 실수한 부분은 locale 파일을 부분적으로 잘못 덮어써서 UI가 다시 영어로 돌아간 점입니다.  
결국 원래 한국어 locale 파일을 기준으로 필요한 key만 최소한으로 바꾸는 방식으로 정리했습니다.

이런 류의 수정은 전체 파일을 무리하게 바꾸기보다, 실제로 필요한 번역 key만 좁게 수정하는 편이 안전합니다.

## 6. GitHub 로그인 추가

익명 댓글만 허용해도 되지만, GitHub 계정으로 남기고 싶은 사람도 있을 수 있어 GitHub OAuth도 추가했습니다.

GitHub에서 OAuth App을 만들 때 callback URL은 아래 형태로 설정합니다.

```text
https://comments.example.com/auth/github/callback
```

서버의 `.env`에는 client id와 client secret을 넣습니다.

```bash
AUTH_GITHUB_CID=<github-client-id>
AUTH_GITHUB_CSEC=<github-client-secret>
```

이 설정을 추가한 뒤 Remark42를 재시작하면, 댓글창에서 GitHub 로그인과 익명 작성을 함께 사용할 수 있습니다.

## 7. 관리자 권한 설정

관리자 권한도 따로 설정했습니다.

처음에는 `ADMIN_PASSWD`가 있으니 바로 모든 댓글을 삭제할 수 있을 것이라 생각했는데, 웹 UI에서 GitHub 로그인 계정을 관리자로 인식시키려면 `ADMIN_SHARED_ID`가 필요했습니다.

Remark42에 GitHub로 한 번 댓글을 작성하면 DB 안에 해당 사용자의 Remark42 user id가 생깁니다.

형태는 대략 아래와 같습니다.

```text
github_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

이 값을 서버 `.env`에 넣었습니다.

```bash
ADMIN_SHARED_ID=<github-user-id-in-remark42>
```

재시작 후 외부 config를 확인하면 `admins` 목록에 해당 ID가 들어간 것을 볼 수 있습니다.

```bash
curl https://comments.example.com/api/v1/config?site=masanam
```

이후 GitHub로 다시 로그인하면 관리자 권한으로 댓글 삭제 같은 작업을 할 수 있습니다.

## 8. Telegram 댓글 알림 연결

마지막으로 새 댓글이 달렸을 때 Telegram으로 알림이 오도록 설정했습니다.

먼저 Telegram의 BotFather에서 새 bot을 만들고 bot token을 발급받았습니다.  
이 token은 매우 민감한 값이므로 절대 저장소에 넣지 않습니다.

그다음 bot에게 `/start` 메시지를 보내고, Bot API의 `getUpdates`로 chat id를 확인했습니다.

```bash
curl https://api.telegram.org/bot<telegram-token>/getUpdates
```

Remark42 서버 `.env`에는 아래 값을 추가했습니다.

```bash
NOTIFY_ADMINS=telegram
TELEGRAM_TOKEN=<telegram-bot-token>
NOTIFY_TELEGRAM_CHAN=<telegram-chat-id>
```

재시작 후 로그에서 아래 메시지를 확인했습니다.

```text
make notify, for users: [none], for admins: [telegram]
```

이 상태가 되면 새 댓글이 달렸을 때 관리자 Telegram으로 알림이 전송됩니다.

## 9. 최종 확인

마지막으로 확인한 항목은 아래와 같습니다.

- `https://comments.masanam.co.kr/web/embed.js` 접근 가능
- 블로그 글에서 댓글창 로드 가능
- 익명 댓글 작성 가능
- GitHub 로그인 가능
- 글별로 댓글이 분리되어 저장됨
- GitHub 로그인 계정이 관리자 권한으로 인식됨
- 관리자 댓글 삭제 가능
- Telegram bot 테스트 메시지 전송 가능
- Remark42 로그에서 관리자 Telegram 알림 활성화 확인

## 정리

이번 작업은 단순히 댓글창을 붙이는 작업이라기보다, 정적 블로그에 작은 댓글 백엔드를 하나 붙이는 작업에 가까웠습니다.

GitHub Pages 자체는 여전히 정적 사이트로 유지하고, 댓글 저장과 인증, 알림은 Oracle Cloud에 올린 Remark42가 담당하게 했습니다.

결과적으로 지금 블로그 댓글은 아래 기능을 갖게 되었습니다.

- 익명 댓글
- GitHub 로그인 댓글
- 관리자 삭제
- 글별 댓글 분리
- Telegram 새 댓글 알림
- 블로그 테마에 맞춘 댓글 UI

개인 블로그에는 이 정도 구성이 꽤 적당한 것 같습니다.  
로그인 장벽은 낮추고, 관리 권한과 알림은 유지할 수 있기 때문입니다.

앞으로 댓글이 실제로 얼마나 달릴지는 모르겠지만, 최소한 이제는 글을 읽다가 궁금한 점이나 오류를 발견한 사람이 조금 더 편하게 남길 수 있는 구조가 되었습니다.

그리고 만든 정성을 봐서.. 댓글 달아주세요 ㅎ

2026-05-08 by Masanam
