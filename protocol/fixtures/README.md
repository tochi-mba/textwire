# Fixtures

Recorded inputs that both test suites and the offline simulator read. `index.json` maps each
URL and search query to its file. Changing a fixture changes the golden vectors in
`../vectors/documents/`; regenerate them with `make vectors`.

| File | What it is | Source and licence |
| --- | --- | --- |
| `pages/article.html` | A news article written for these tests, with every construct the cleanup handles: navigation, images, citations, relative, fragment, `mailto:` and `javascript:` links, a repeated link, lists, a table, a quote. | Written for textwire; MIT like the rest of the repository. The newspaper and people are fictional. |
| `pages/wikipedia-sms-gateway.html` | The Wikipedia article "SMS gateway", recorded 2026-09-30, with `<script>`, `<style>` and `<link>` elements removed to keep it small. | [Wikipedia](https://en.wikipedia.org/wiki/SMS_gateway), CC BY-SA 4.0, by its contributors. |
| `pages/notes.txt` | A plain-text page, to exercise the `text/plain` path. | Written for textwire. |
| `searches/bbc-weather-london.json` | The five results the `ddgs` package returned for "bbc weather london" on 2026-09-30, as its raw dictionaries. | Search result titles and snippets belong to the linked sites; recorded for testing only. |
