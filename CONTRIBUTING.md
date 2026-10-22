# Contributing to CampusFlow

Thanks for helping improve the CampusFlow prototype. The project is currently an educational demonstration, not an official attendance service.

## Before opening an issue or pull request

- Search existing issues to avoid duplicates.
- Describe a reproducible problem or a focused improvement.
- Use fictional data only. Never submit student information, credentials, private campus addresses, internal network details, or screenshots containing sensitive records.
- Be explicit about the prototype's limitations. A QR scan is not proof of identity or physical presence.

## Local checks

```bash
python -m pip install -r requirements.txt
python -m py_compile server.py tests/test_smoke.py
node --check app.js
python -m unittest discover -s tests -v
```

## Scope

Small, reviewable changes are best. Production authentication, official roster integration, privacy controls and deployment security require institutional requirements and review; they should not be represented as solved by a UI-only change.




