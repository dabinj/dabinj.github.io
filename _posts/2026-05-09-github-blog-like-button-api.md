---
title: "Github 블로그에 좋아요 버튼 구현하기 (With API)"
date: 2026-05-09 21:55:00 +0900
description: "GitHub Pages 블로그에 글별 좋아요 버튼을 추가하고 Oracle Cloud 서버 API와 SQLite로 좋아요 수를 저장한 과정"
author: dabin
categories: [Project]
tags: [github-pages, jekyll, like-button, api, oracle-cloud, sqlite]
---

지난번에는 GitHub Pages 블로그에 익명 댓글 기능을 붙였습니다.

Remark42를 Oracle Cloud 서버에 올리고, 블로그에서는 댓글창만 불러오는 방식이었습니다.  
이 작업을 하고 나니 한 가지 생각이 들었습니다.

댓글 서버를 직접 운영할 수 있다면, 글마다 **좋아요 버튼**도 직접 만들 수 있지 않을까?

GitHub Pages는 정적 사이트라서 서버에 값을 저장하는 기능이 없습니다. 하지만 이미 Oracle Cloud 서버와 Caddy, Docker 구성이 있으니 작은 API 하나를 더 붙이면 좋아요 수를 저장할 수 있습니다.

이번 글은 GitHub Pages 블로그에 글별 좋아요 버튼을 붙이고, 좋아요 수를 Oracle Cloud 서버의 SQLite에 저장하도록 만든 과정을 정리한 기록입니다.

## 목표

이번에 구현하고 싶었던 기능은 단순했습니다.

- 각 글마다 좋아요 버튼이 있어야 한다.
- 좋아요 수는 모든 방문자에게 같은 값으로 보여야 한다.
- 좋아요 수는 Oracle Cloud 서버에 저장되어야 한다.
- 글별로 좋아요 수가 분리되어야 한다.
- 한 브라우저에서는 좋아요를 한 번 누르면 다시 누를 때 취소되도록 한다.
- 처음에는 복잡한 로그인 없이 가볍게 구현한다.

처음에는 로컬 테스트용으로 `localStorage`에만 좋아요 수를 저장했습니다.

하지만 이 방식은 현재 브라우저에서만 값이 보입니다.  
다른 사람에게는 공유되지 않고, 다른 브라우저에서 열면 다시 0으로 보입니다.

그래서 최종적으로는 아래처럼 바꾸었습니다.

```text
좋아요 버튼 클릭
  |
  |  GET / POST
  v
comments.masanam.co.kr/api/likes
  |
  |  Caddy reverse proxy
  v
likes-api Docker container
  |
  |  글 URL별 count 저장
  v
SQLite
```

## 전체 구조

블로그는 여전히 GitHub Pages에서 정적으로 배포됩니다.

좋아요 버튼은 Jekyll include로 각 포스트에 삽입하고, 실제 카운트 조회와 저장은 Oracle Cloud 서버에 만든 API가 담당합니다.

```text
GitHub Pages / Jekyll
  |
  |  _includes/post-like.html
  v
사용자 브라우저
  |
  |  fetch()
  v
https://comments.masanam.co.kr/api/likes
  |
  |  Caddy route
  v
likes-api
  |
  v
likes.db
```

댓글 기능을 위해 이미 `comments.masanam.co.kr` 도메인을 사용하고 있었기 때문에, 좋아요 API도 같은 도메인 아래에 붙였습니다.

```text
https://comments.masanam.co.kr/api/likes
```

## 1. API 설계

필요한 API는 두 개면 충분했습니다.

```text
GET /api/likes?url=/posts/example/
```

현재 글의 좋아요 수를 조회합니다.

응답은 아래 형태입니다.

```json
{
  "url": "/posts/example/",
  "count": 3
}
```

좋아요를 누르거나 취소할 때는 `POST`를 사용했습니다.

```text
POST /api/likes
```

요청 body는 아래처럼 보냅니다.

```json
{
  "url": "/posts/example/",
  "action": "like"
}
```

취소할 때는 `action`을 `unlike`로 보냅니다.

```json
{
  "url": "/posts/example/",
  "action": "unlike"
}
```

글을 구분하는 key는 `page.url`입니다.  
예를 들어 이 글의 URL이 `/posts/github-blog-like-button-api/`라면, 이 값이 좋아요 저장 key가 됩니다.

## 2. SQLite로 저장하기

좋아요 수만 저장하면 되기 때문에 별도의 큰 데이터베이스는 필요하지 않았습니다.

SQLite 하나면 충분하다고 판단했습니다.

테이블 구조는 단순합니다.

```sql
CREATE TABLE IF NOT EXISTS post_likes (
  url TEXT PRIMARY KEY,
  count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

`url`을 primary key로 두고, 각 글의 좋아요 수를 `count`에 저장합니다.

좋아요를 누르면 `count + 1`, 취소하면 `count - 1`을 합니다.  
다만 0 아래로 내려가지 않도록 처리했습니다.

```sql
UPDATE post_likes
SET count = CASE WHEN count > 0 THEN count - 1 ELSE 0 END,
    updated_at = ?
WHERE url = ?;
```

## 3. likes-api 컨테이너 추가

Oracle Cloud 서버에는 이미 Remark42와 Caddy가 Docker Compose로 올라가 있었습니다.

여기에 `likes-api` 서비스를 하나 더 추가했습니다.

```yaml
likes-api:
  image: python:3.12-alpine
  container_name: masanam-likes-api
  restart: unless-stopped
  command: python /app/likes_api.py
  environment:
    - LIKES_DB=/data/likes.db
  volumes:
    - ./likes_app:/app:ro
    - ./likes_data:/data
```

API 코드는 `likes_app`에 두고, SQLite 데이터는 `likes_data`에 저장하도록 했습니다.

컨테이너를 재시작해도 좋아요 수가 사라지면 안 되기 때문에 DB 파일은 volume으로 분리했습니다.

## 4. Caddy 라우팅 추가

댓글 기능은 Remark42가 처리하고, 좋아요 API는 새로 만든 `likes-api`가 처리해야 합니다.

그래서 Caddyfile에 `/api/likes` 경로만 `likes-api`로 보내는 라우팅을 추가했습니다.

```caddy
comments.masanam.co.kr {
  encode gzip zstd

  @remark_web path /web/*
  header @remark_web Cache-Control "no-store, no-cache, must-revalidate, max-age=0"

  @likes_api path /api/likes /api/likes/*
  reverse_proxy @likes_api likes-api:8090

  reverse_proxy remark42:8080
}
```

이렇게 하면 같은 도메인 안에서 역할이 나뉩니다.

```text
/web/embed.js       -> Remark42
/api/v1/...         -> Remark42
/api/likes          -> likes-api
나머지 요청         -> Remark42
```

## 5. Jekyll에 좋아요 버튼 추가

블로그 쪽에는 `_includes/post-like.html` 파일을 만들었습니다.

버튼은 아주 단순합니다.

```html
<section
  class="post-like"
  data-post-like
  data-post-url="{{ page.url | relative_url }}"
  data-like-endpoint="{{ site.comments.remark42.host }}/api/likes"
>
  <button class="post-like__button" type="button" aria-pressed="false" data-post-like-button>
    <i class="far fa-heart" aria-hidden="true"></i>
    <span>좋아요</span>
    <strong data-post-like-count>0</strong>
  </button>
</section>
```

여기서 중요한 값은 두 개입니다.

```text
data-post-url
data-like-endpoint
```

`data-post-url`은 현재 글의 URL이고, `data-like-endpoint`는 좋아요 API 주소입니다.

이 include는 `_layouts/post.html`에서 본문 아래에 넣었습니다.

이렇게 하면 모든 포스트에 자동으로 좋아요 버튼이 붙습니다.

## 6. 프론트엔드 동작

페이지가 열리면 먼저 현재 글의 좋아요 수를 조회합니다.

```javascript
requestLike('GET')
  .then((data) => {
    count = normalizeCount(data.count);
    render(count, liked);
  });
```

버튼을 누르면 좋아요 또는 취소 요청을 보냅니다.

```javascript
const data = await requestLike('POST', {
  url: postUrl,
  action: nextLiked ? 'like' : 'unlike'
});
```

응답으로 돌아온 count를 기준으로 화면을 다시 그립니다.

```javascript
count = normalizeCount(data.count);
render(count, liked);
```

한 브라우저에서 이미 눌렀는지 여부는 `localStorage`에 저장했습니다.

```javascript
const likedKey = `masanam:server-likes:${postUrl}:liked`;
```

이 값은 중복 클릭을 막기 위한 UI 상태에 가깝습니다.  
실제 좋아요 수는 서버의 SQLite에 저장됩니다.

## 7. 운영 배포에서 만난 문제

로컬에서는 좋아요 버튼이 잘 작동했는데, 정식 서버에 배포하고 나니 버튼은 보이지만 클릭해도 숫자가 올라가지 않는 문제가 있었습니다.

처음에는 API 문제라고 생각했습니다.  
그래서 서버에서 직접 아래 흐름을 확인했습니다.

```text
GET /api/likes
OPTIONS /api/likes
POST /api/likes
```

`curl`로 직접 요청하면 count가 정상적으로 증가했습니다.  
즉 API 서버와 SQLite 저장 자체는 문제가 아니었습니다.

문제는 브라우저에서 버튼을 눌렀을 때 `POST /api/likes` 요청이 서버 로그에 찍히지 않는다는 점이었습니다.  
이 말은 브라우저에서 클릭 이벤트가 제대로 붙지 않았거나, 최신 JavaScript가 실행되지 않고 있다는 뜻이었습니다.

확인해보니 두 가지 문제가 겹쳐 있었습니다.

첫 번째는 PWA service worker 캐시였습니다.  
GitHub Pages에 배포된 최신 HTML을 받아와야 하는데, 기존 service worker가 예전 포스트 HTML을 잡고 있을 수 있었습니다. 좋아요 버튼 코드는 포스트 HTML 안에 inline script로 들어가 있었기 때문에, HTML 캐시가 남아 있으면 최신 수정이 반영되지 않았습니다.

그래서 우선 `_config.yml`에서 PWA를 껐습니다.

```yaml
pwa:
  enabled: false
```

이렇게 하면 운영 페이지에는 `/app.js` 대신 `/unregister.js`가 들어가고, 기존 service worker를 해제하게 됩니다.

두 번째 문제가 진짜 핵심이었습니다.

운영 배포에서는 HTML이 한 줄로 압축됩니다. 그런데 좋아요 버튼의 inline script 안에 아래와 같은 JavaScript 한 줄 주석이 있었습니다.

```javascript
// Ignore storage errors so the server count still works.
```

로컬 개발 서버에서는 줄바꿈이 유지되기 때문에 문제가 없었습니다.  
하지만 production build에서는 HTML과 script가 압축되면서 이 `//` 주석 뒤쪽의 JavaScript가 같은 줄에 붙어버렸고, 결과적으로 뒤쪽 코드가 주석 처리되었습니다.

즉 버튼 클릭 이벤트를 등록하는 코드까지 실행되지 않았던 것입니다.

해결은 단순했습니다. inline script 안에서는 `//` 주석을 쓰지 않도록 바꾸었습니다.

```javascript
} catch (error) {}
```

이 문제를 겪고 나니, Jekyll처럼 HTML 압축이 들어가는 환경에서는 inline JavaScript 안의 `//` 주석을 조심해야 한다는 것을 배웠습니다.  
가능하면 inline script는 짧게 유지하거나, 별도 JS 파일로 분리하는 편이 더 안전할 것 같습니다.

## 8. 현재 방식의 한계

이번 구현은 일단 간단한 MVP입니다.

그래서 한계도 분명합니다.

- 로그인 기반 좋아요는 아니다.
- 브라우저를 바꾸면 다시 누를 수 있다.
- API를 직접 반복 호출하는 악의적 요청까지 완전히 막지는 않는다.
- IP 기반 rate limit은 아직 넣지 않았다.
- 좋아요 알림을 Telegram으로 보내는 기능은 아직 넣지 않았다.

개인 블로그의 가벼운 좋아요 기능으로는 이 정도도 충분하다고 봤습니다.

나중에 필요하면 아래 기능을 추가할 수 있습니다.

- IP 기반 rate limit
- 하루 1회 제한
- Cloudflare Turnstile 같은 간단한 abuse 방지
- 관리자용 좋아요 통계 페이지
- 글 목록에서 좋아요 수 표시

## 9. 테스트

API는 먼저 `curl`로 확인했습니다.

```bash
curl "https://comments.masanam.co.kr/api/likes?url=/posts/example/"
```

응답은 아래처럼 돌아옵니다.

```json
{
  "url": "/posts/example/",
  "count": 0
}
```

좋아요를 누르는 요청도 확인했습니다.

```bash
curl -X POST "https://comments.masanam.co.kr/api/likes" \
  -H "Content-Type: application/json" \
  -d '{"url":"/posts/example/","action":"like"}'
```

응답에서 count가 증가하면 서버 저장이 정상적으로 된 것입니다.

Jekyll 빌드도 함께 확인했습니다.

```bash
BUNDLE_PATH=vendor/bundle bundle exec jekyll build
```

로컬 서버에서 글을 열어 좋아요 버튼이 보이고, 클릭할 때 서버 API로 요청이 가는 것까지 확인했습니다.

운영 배포 후에는 Oracle 서버에서 API 로그를 확인했습니다.

```bash
docker logs --since 3m masanam-likes-api
```

정상적으로 작동하면 버튼을 눌렀을 때 아래와 같은 요청이 찍힙니다.

```text
GET /api/likes
OPTIONS /api/likes
POST /api/likes
```

이번에는 로컬 테스트만으로 끝내지 않고, 운영 페이지에서 실제 버튼을 눌렀을 때 `POST /api/likes`가 서버 로그에 들어오는지까지 확인하는 것이 중요했습니다.

## 정리

이번 작업으로 블로그 글마다 좋아요 버튼이 붙었습니다.

처음에는 로컬 테스트용으로 브라우저에만 저장했지만, 최종적으로는 Oracle Cloud 서버에 작은 API를 만들고 SQLite에 글별 좋아요 수를 저장하도록 바꾸었습니다.

구조는 단순합니다.

```text
Jekyll post
  -> post-like.html
  -> fetch('/api/likes')
  -> likes-api
  -> SQLite
```

개인 블로그에는 너무 무거운 기능보다 이런 작은 기능을 하나씩 직접 붙여보는 재미가 있는 것 같습니다.

댓글 기능을 붙였을 때도 느꼈지만, 정적 블로그라도 작은 서버 하나를 옆에 두면 생각보다 할 수 있는 일이 많아집니다.

이제 글을 읽고 공감되면 댓글까지는 아니더라도 좋아요 한 번 정도는 남길 수 있게 되었습니다.

2026-05-09 by Masanam
