# Markdown link checking

Run the deterministic local checker from the repository root:

```bash
python tools/check_markdown_links.py
```

It validates relative Markdown targets and same-document or linked-document
heading anchors. It ignores external URLs, email links, images, and links inside
fenced code blocks.

External URL checking is separate because it requires network access, can be
flaky, and may disclose requested URLs.
