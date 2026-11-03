# Security

Murmury hears your calls and holds your documents and API keys, so security reports matter.

**Report a vulnerability privately** through GitHub: the repository's Security tab, "Report a vulnerability".
Please don't open a public issue for it. You'll get a reply within a few days.

What the app is built to guarantee, and what is worth reporting if it fails:

- Audio never leaves the Mac; only the text of a question and your documents go to the AI service you chose.
- Nothing about a call is written to disk.
- API keys stay in the macOS Keychain.
- The floating window stays out of screen capture (`scripts/check_hidden.py` measures it).

Releases are built on the maintainer's Mac and published only as GitHub Releases of this repository.
The SHA-256 of each `Murmury.dmg` is in its release notes.
