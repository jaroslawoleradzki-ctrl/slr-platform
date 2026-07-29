# SLR Platform — Application Versioning Policy

## 1. Application-Wide Single Version Policy

**SLR Platform** uses a unified application-wide versioning model. A single version number applies to the entire platform, including backend modules, frontend GUI, API schemas, and infrastructure configs.

- Frontend and backend do **NOT** maintain independent, decoupled product version numbers.
- Every accepted functional increment of SLR Platform receives the next unified platform version.

---

## 2. Single Source of Truth (`VERSION`)

The root directory file `VERSION` is the **single source of truth** for the version of SLR Platform:

```text
0.1.0
```

Natively supported tool configs (e.g. `frontend/package.json`, `pyproject.toml`) synchronize with `VERSION`, but `VERSION` remains the master reference.

---

## 3. Semantic Versioning Pre-1.0 Rules

Version numbers follow Semantic Versioning (`MAJOR.MINOR.PATCH`), adapted for iterative pre-1.0 development:

- `0.MINOR.0` — New accepted functional increment across the platform (e.g., `0.1.0` Application Versioning & Release Identity, `0.2.0` Duplicate Review Backend Integration).
- `0.MINOR.PATCH` — Bug fixes or hotfixes within an existing functional increment (e.g., `0.1.1`).
- `1.0.0` — First stable release ready for end-user systematic literature reviews in production environments.

> [!NOTE]
> Documentation changes within the same increment do **NOT** bump the application version number.

---

## 4. Build-Time Ingestion in Frontend

In `frontend/vite.config.ts`, Vite reads `../VERSION` during build time and injects it as a global compile-time constant `__APP_VERSION__`:

```ts
define: {
  __APP_VERSION__: JSON.stringify(appVersion),
}
```

If the `VERSION` file is unreadable or empty, Vite safely falls back to `'development'` without crashing.

---

## 5. Presentation in GUI & Release Identity

The application version is presented in two primary locations in the GUI:

1. **Application Shell (Sidebar & Header)**:
   - Header displays `SLR Platform v0.1.0` alongside the runtime mode badge (`Mock API / Demo Data`).
   - Sidebar footer displays `SLR Platform v0.1.0`.

2. **About Application Dialog (`AboutModal`)**:
   - Product Name: **SLR Platform**
   - Version: **0.1.0** (derived from `__APP_VERSION__`)
   - Release Status: **Development Preview**
   - Runtime Mode: **Mock API / Demo Data**
   - Statement: Backend remains single source of truth for domain logic.

---

## 6. Unautomated Elements & Future Scope

The following capabilities are deferred and not automated in Phase 6.2:
- Automated GitHub Releases creation,
- CI/CD build-time release pipelines,
- Automated Git tag creation,
- FastAPI `/version` backend endpoint,
- Automated changelog generation from git commits.
