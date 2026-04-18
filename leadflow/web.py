from __future__ import annotations

from leadflow.api.app import create_app


def main() -> None:
    app = create_app()
    app.run(host="0.0.0.0", port=8081, debug=True)


if __name__ == "__main__":
    main()
