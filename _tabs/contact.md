---
title: Contact
icon: fas fa-envelope
order: 5
---

{% assign formspree_endpoint = site.contact.formspree.endpoint %}
{% assign subject_prefix = site.contact.formspree.subject_prefix | default: "[Private Contact]" %}
{% assign success_message = site.contact.formspree.success_message | default: "문의가 전송되었습니다." %}

비공개 문의는 이 페이지를 통해 따로 남길 수 있습니다.

공개로 남겨도 되는 내용은 각 글 아래 댓글을 이용하고, 개인적으로 보내고 싶은 내용은 아래 폼을 사용하면 됩니다.

{% if formspree_endpoint and formspree_endpoint != "" %}
<div class="contact-form-card">
  <form
    id="private-contact-form"
    class="private-contact-form"
    action="{{ formspree_endpoint }}"
    method="POST"
  >
    <input type="hidden" name="_subject" value="{{ subject_prefix }}">
    <input type="hidden" name="_captcha" value="false">

    <div class="contact-field">
      <label for="contact-name">이름</label>
      <input id="contact-name" name="name" type="text" placeholder="보내는 분 이름">
    </div>

    <div class="contact-field">
      <label for="contact-reply">답장받을 이메일</label>
      <input id="contact-reply" name="email" type="email" placeholder="name@example.com">
    </div>

    <div class="contact-field">
      <label for="contact-subject">제목</label>
      <input id="contact-subject" name="subject" type="text" placeholder="문의 제목" required>
    </div>

    <div class="contact-field">
      <label for="contact-message">내용</label>
      <textarea id="contact-message" name="message" rows="8" placeholder="문의 내용을 적어 주세요." required></textarea>
    </div>

    <div class="contact-field form-honeypot" aria-hidden="true">
      <label for="contact-company">회사</label>
      <input id="contact-company" name="_gotcha" type="text" tabindex="-1" autocomplete="off">
    </div>

    <div class="contact-actions">
      <button type="submit" class="btn btn-primary">비공개 문의 보내기</button>
      <p class="contact-help">문의 내용은 Formspree를 통해 비공개로 전달됩니다. 사이트에는 메일 주소가 노출되지 않습니다.</p>
      <p id="contact-status" class="contact-status" role="status" aria-live="polite"></p>
    </div>
  </form>
</div>

<script>
  document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('private-contact-form');
    const status = document.getElementById('contact-status');

    if (!form) {
      return;
    }

    form.addEventListener('submit', async function (event) {
      event.preventDefault();

      const submitButton = form.querySelector('button[type="submit"]');
      const formData = new FormData(form);

      if (status) {
        status.textContent = '전송 중입니다...';
        status.classList.remove('is-error', 'is-success');
      }

      submitButton.disabled = true;

      try {
        const response = await fetch(form.action, {
          method: 'POST',
          body: formData,
          headers: {
            Accept: 'application/json'
          }
        });

        if (!response.ok) {
          throw new Error('Form submission failed');
        }

        form.reset();

        if (status) {
          status.textContent = '{{ success_message }}';
          status.classList.add('is-success');
        }
      } catch (error) {
        if (status) {
          status.textContent = '문의 전송에 실패했습니다. 잠시 후 다시 시도해 주세요.';
          status.classList.add('is-error');
        }
      } finally {
        submitButton.disabled = false;
      }
    });
  });
</script>
{% else %}
> 비공개 문의 폼은 준비해 두었습니다. 실제 발송을 쓰려면 `_config.yml` 의 `contact.formspree.endpoint` 에 Formspree 엔드포인트를 넣어 주세요.
{% endif %}
