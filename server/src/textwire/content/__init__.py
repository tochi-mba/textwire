"""The content pipeline: from a URL or a query to a document ready to paginate.

Fetching and searching sit behind interfaces with fakes (:mod:`textwire.content.fakes`), so
everything after them is deterministic and tested against recorded fixtures.
"""
