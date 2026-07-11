"""List all registered routes."""
import app

for r in app.app.routes:
    methods = getattr(r, "methods", None)
    path = getattr(r, "path", "<no path attr>")
    print(f"{path:40s} {sorted(methods) if methods else ''}  {type(r).__name__}")
