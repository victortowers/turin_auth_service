# Penetration Test Instructions (Strix)

## Credentials
- Session Cookie: Available (via environment variables under SESSION_COOKIE).

- OSM Nodes (to test): 1871769061, 31935580, 1871768924, 4363722848, 245374595

- _Note for OSM: At least **ONE** pair of OSM nodes should work. If they don't work, stop the task immediately and mark as failed, citing OSM routing or OSM node failures._
-
## Focus Areas (OWASP)
1. Security Misconfiguration (OWASP A02:2025)
1. Insecure Design (OWASP A06:2025)
3. JWT token manipulation or Authentication Failures (OWASP A07:2025)

## Out of Scope
- /health endpoint(s)
- Firebase JWT Validations (check_revoked=true is to be implemented in sensitive operations only, we do not wish to break the entire server due to a Firebase Failure)
