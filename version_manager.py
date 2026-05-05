"""
Gestor de versiones para figuras SVG.
Guarda un snapshot automático antes de cada edición, permitiendo
al estudiante volver a cualquier estado anterior si la figura se rompe.
"""

import json
from datetime import datetime
from pathlib import Path


class VersionManager:
    """Maneja el historial de versiones de un archivo SVG.

    Estructura en disco:
        ~/mcp_draw_figures/
        ├── figura_YYYYMMDD_HHMMSS.svg        ← archivo activo
        └── .versions/
            └── figura_YYYYMMDD_HHMMSS/
                ├── v001.svg
                ├── v002.svg
                └── history.json
    """

    def __init__(self, svg_path: str):
        self._svg = Path(svg_path)
        self._dir = self._svg.parent / ".versions" / self._svg.stem
        self._history_file = self._dir / "history.json"
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── persistencia ─────────────────────────────────────────────────────────

    def _load(self) -> list[dict]:
        if not self._history_file.exists():
            return []
        return json.loads(self._history_file.read_text(encoding="utf-8"))

    def _save(self, history: list[dict]) -> None:
        self._history_file.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _path(self, num: int) -> Path:
        return self._dir / f"v{num:03d}.svg"

    # ── API pública ───────────────────────────────────────────────────────────

    def save(self, comment: str | None = None) -> int:
        """Guarda el estado actual del SVG como nueva versión.

        Returns:
            Número de versión asignado.
        """
        if not self._svg.exists():
            raise FileNotFoundError(f"SVG no encontrado: {self._svg}")

        history = self._load()
        num = len(history) + 1

        self._path(num).write_bytes(self._svg.read_bytes())

        history.append({
            "version": num,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "comment": comment or f"Versión {num}",
            "size_bytes": self._svg.stat().st_size,
        })
        self._save(history)
        return num

    def list(self) -> list[dict]:
        """Retorna el historial completo de versiones."""
        return self._load()

    def count(self) -> int:
        return len(self._load())

    def get_path(self, num: int) -> Path:
        """Retorna la ruta al SVG de una versión específica."""
        path = self._path(num)
        history = self._load()

        if num < 1 or num > len(history):
            raise ValueError(
                f"Versión {num} no existe. "
                f"Hay {len(history)} versión(es) guardada(s)."
            )
        if not path.exists():
            raise FileNotFoundError(f"Archivo de versión {num} no encontrado en disco.")

        return path

    def restore(self, num: int) -> dict:
        """Restaura una versión anterior al archivo SVG activo.

        Guarda el estado actual como nueva versión antes de restaurar,
        para que nunca se pierda trabajo.

        Returns:
            Dict con info de la versión restaurada y la versión de respaldo.
        """
        history = self._load()

        if num < 1 or num > len(history):
            raise ValueError(
                f"Versión {num} no existe. "
                f"Hay {len(history)} versión(es) guardada(s)."
            )

        # Guardar estado actual antes de restaurar
        backup_num = self.save(comment=f"Respaldo automático antes de restaurar v{num}")

        # Restaurar versión pedida
        restored_content = self._path(num).read_bytes()
        self._svg.write_bytes(restored_content)

        # Registrar la restauración como nueva versión
        new_num = self.save(comment=f"Restauración de v{num}")

        return {
            "restored_version": num,
            "backup_version": backup_num,
            "new_version": new_num,
            "original_comment": history[num - 1]["comment"],
            "original_timestamp": history[num - 1]["timestamp"],
        }
