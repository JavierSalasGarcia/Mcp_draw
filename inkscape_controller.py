"""
Controlador de Inkscape para Windows.
Gestiona apertura, recarga y exportación mediante la CLI de Inkscape.
"""

import subprocess
import platform
from pathlib import Path


_INKSCAPE_WINDOWS = [
    r"C:\Program Files\Inkscape\bin\inkscape.exe",
    r"C:\Program Files (x86)\Inkscape\bin\inkscape.exe",
    r"C:\Program Files\Inkscape\inkscape.exe",
    r"C:\Program Files (x86)\Inkscape\inkscape.exe",
]


class InkscapeController:
    def __init__(self):
        self._exe = self._find()
        self._process: subprocess.Popen | None = None

    # ── detección ─────────────────────────────────────────────────────────────

    def _find(self) -> str | None:
        if platform.system() == "Windows":
            for p in _INKSCAPE_WINDOWS:
                if Path(p).exists():
                    return p
        # Intento en PATH (Linux/Mac o Windows con Inkscape en PATH)
        try:
            r = subprocess.run(
                ["inkscape", "--version"],
                capture_output=True,
                timeout=5,
            )
            if r.returncode == 0:
                return "inkscape"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def available(self) -> bool:
        return self._exe is not None

    def _not_found_msg(self, svg_path: str) -> str:
        return (
            "Inkscape no encontrado. Descárgalo en https://inkscape.org\n"
            f"El archivo SVG fue guardado en: {svg_path}\n"
            "Ábrelo manualmente en Inkscape para editarlo."
        )

    # ── ciclo de vida del proceso ─────────────────────────────────────────────

    def _close_current(self):
        """Cierra la instancia de Inkscape abierta por el MCP, si existe."""
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None

    def _launch(self, svg_path: str) -> subprocess.Popen:
        return subprocess.Popen(
            [self._exe, svg_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # ── API pública ───────────────────────────────────────────────────────────

    def open_file(self, svg_path: str) -> str:
        """Abre un archivo SVG en Inkscape."""
        if not self.available():
            return self._not_found_msg(svg_path)

        self._close_current()
        self._process = self._launch(svg_path)
        return f"Abierto en Inkscape (PID {self._process.pid})"

    def reload_file(self, svg_path: str) -> str:
        """Cierra y vuelve a abrir el SVG actualizado en Inkscape."""
        if not self.available():
            return f"SVG actualizado en: {svg_path} (ábrelo manualmente en Inkscape)"

        self._close_current()
        self._process = self._launch(svg_path)
        return f"Inkscape recargado con la figura actualizada (PID {self._process.pid})"

    def export_file(self, svg_path: str, output_path: str, fmt: str) -> str:
        """Exporta el SVG al formato indicado usando la CLI de Inkscape."""
        if not self.available():
            return (
                f"Inkscape no encontrado. No se puede exportar automáticamente.\n"
                f"Abre {svg_path} en Inkscape y exporta manualmente a {fmt.upper()}."
            )

        valid_formats = {"pdf", "png", "svg", "eps", "emf"}
        if fmt.lower() not in valid_formats:
            return f"Formato no soportado: {fmt}. Usa: {', '.join(sorted(valid_formats))}"

        try:
            result = subprocess.run(
                [
                    self._exe,
                    svg_path,
                    f"--export-type={fmt.lower()}",
                    f"--export-filename={output_path}",
                ],
                capture_output=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return "Tiempo de exportación agotado. Intenta exportar manualmente desde Inkscape."

        if result.returncode == 0:
            return f"Exportado exitosamente: {output_path}"

        err = result.stderr.decode(errors="replace").strip()
        return f"Error al exportar: {err or 'Error desconocido de Inkscape'}"
