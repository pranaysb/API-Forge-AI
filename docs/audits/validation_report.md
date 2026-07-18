# Validation Strategy Report

This report identifies the validation mode that will be applied to each endpoint in the current OpenAPI specification.

## Endpoints

| Method | Path | Validation Mode | Reason |
|---|---|---|---|
| `GET` | `/users/1` | **REAL (if Auth Provided) / SYNTHETIC (No Auth)** | GET is safe, depends on Auth state. |
| `GET` | `/posts/1` | **REAL (if Auth Provided) / SYNTHETIC (No Auth)** | GET is safe, depends on Auth state. |