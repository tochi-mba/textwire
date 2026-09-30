# ADR-0008: Links become numbered chips; the server keeps the URLs

**Status:** Accepted (2026-09-30)

## Context

A web page's links are what make it browsable, and URLs are long: a page with thirty links
can spend more bytes on URLs than on text. Sending them all to the phone costs money for
links that will never be followed.

## Decision

The server rewrites every link in an extracted page to its anchor text followed by a number
in brackets, `like this[3]`, and keeps the page's link table in its database. To follow a
link the phone sends `l <tag> 3`, and the server looks the URL up. Numbers are assigned in
reading order, a repeated URL keeps its first number, and a page keeps at most 60 links;
later ones become plain text. Citation markers such as `[12]` in the source text are removed
so that any `[n]` the phone sees is a link.

## Why

- A link costs three or four bytes in the page instead of fifty to a hundred.
- Following a link costs a request of about ten characters, which is free on the owner's
  plan.
- The phone never needs to parse or display a URL.

## What it costs

- The server must keep link tables for as long as pages can be followed:
  `TEXTWIRE_RETENTION_HOURS`, 24 by default.
- The phone cannot show where a link goes before following it. A search result shows the
  site's domain in the text instead.

## What would change our minds

A need to share links out of the app, which would add a verb to ask the server for one URL.
