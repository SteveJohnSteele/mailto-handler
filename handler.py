#!/usr/bin/env python3
"""Open a mailto: link in the webmail and browser chosen in the settings.

Standard library only, and short-lived: it works even when the tray app
isn't running. Nothing is sent; the webmail just opens a draft.
"""
import sys

import browsers
import config
import providers


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        browsers.show_error("No mailto: link was supplied.")
        return 2
    cfg = config.load()
    provider = providers.find_provider(cfg)
    try:
        url = providers.build_url(provider, argv[0])
    except ValueError:
        browsers.show_error("Not a mailto: link:\n%s" % argv[0][:200])
        return 2
    problem = browsers.open_url(cfg, url)
    if problem:
        browsers.show_error(problem)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
