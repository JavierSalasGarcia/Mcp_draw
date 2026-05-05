"""
Utilidades para procesamiento y análisis de SVG.
"""

import re
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET


# ── limpieza de respuestas de Claude ─────────────────────────────────────────

def clean_svg_response(text: str) -> str:
    """Extrae SVG limpio de una respuesta de Claude.

    Claude a veces envuelve el SVG en bloques markdown (```svg ... ```).
    """
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()

    svg_start = text.find("<svg")
    if svg_start > 0:
        text = text[svg_start:]

    return text


# ── renderizado ───────────────────────────────────────────────────────────────

def render_svg_to_png(
    svg_path: str,
    output_path: str,
    width: int,
    inkscape_exe: str | None,
) -> str | None:
    """Renderiza un SVG a PNG usando Inkscape CLI.

    Returns:
        None si tuvo éxito, mensaje de error si falló.
    """
    if not inkscape_exe:
        return (
            "Inkscape no encontrado. Instálalo desde https://inkscape.org "
            "para habilitar la vista previa visual."
        )

    try:
        result = subprocess.run(
            [
                inkscape_exe,
                svg_path,
                "--export-type=png",
                f"--export-filename={output_path}",
                f"--export-width={width}",
            ],
            capture_output=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "Tiempo de renderizado agotado (>30s)."
    except FileNotFoundError:
        return f"Inkscape no encontrado en: {inkscape_exe}"

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        return stderr or f"Inkscape terminó con código {result.returncode}"

    if not Path(output_path).exists():
        return "Inkscape no generó el archivo PNG."

    return None  # éxito


# ── validación ────────────────────────────────────────────────────────────────

def validate_svg_detailed(content: str) -> str:
    """Valida la sintaxis y estructura del SVG.

    Revisa:
    - XML bien formado
    - Presencia de viewBox
    - Elementos con id semántico
    - Definición de marcadores de flecha (recomendado)
    """
    issues: list[str] = []
    warnings: list[str] = []

    # Validación de XML
    clean = re.sub(r'\s+xmlns(?::[a-z]+)?="[^"]*"', "", content)
    clean = re.sub(r"<(/?)([a-z]+):", r"<\1", clean)

    try:
        root = ET.fromstring(clean)
    except ET.ParseError as e:
        return f"❌ Error de XML: {e}\n\nEl SVG no se puede parsear. Usa edit_figure() para regenerarlo."

    # viewBox
    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if tag == "svg" and not root.get("viewBox"):
        warnings.append("Sin atributo viewBox — la figura podría no escalar correctamente")

    # Contar elementos con id semántico
    all_ids = [e.get("id", "") for e in root.iter() if e.get("id")]
    semantic_ids = [
        i for i in all_ids
        if any(i.startswith(p) for p in
               ("block-", "arrow-", "label-", "node-", "decision-", "layer-"))
    ]

    if not semantic_ids:
        warnings.append(
            "Ningún elemento tiene id semántico (block-*, arrow-*, label-*, etc.). "
            "Las ediciones por descripción pueden ser menos precisas."
        )

    # Marcador de flecha
    has_marker = "<marker" in content
    if not has_marker:
        warnings.append(
            "No se encontraron marcadores de flecha en <defs>. "
            "Las flechas pueden carecer de punta."
        )

    # Construir reporte
    lines: list[str] = []

    if not issues and not warnings:
        lines.append("✅ SVG válido — sin problemas detectados.")
    else:
        if issues:
            lines.append(f"❌ Errores ({len(issues)}):")
            lines.extend(f"   • {e}" for e in issues)
        if warnings:
            lines.append(f"⚠️  Advertencias ({len(warnings)}):")
            lines.extend(f"   • {w}" for w in warnings)

    lines.append("")
    lines.append(f"Elementos totales: {sum(1 for _ in root.iter())}")
    lines.append(f"IDs semánticos:    {len(semantic_ids)}")
    lines.append(f"IDs totales:       {len(all_ids)}")

    if semantic_ids:
        lines.append(f"IDs encontrados:   {', '.join(semantic_ids[:10])}")
        if len(semantic_ids) > 10:
            lines.append(f"                   ... y {len(semantic_ids) - 10} más")

    return "\n".join(lines)


# ── optimización ──────────────────────────────────────────────────────────────

def optimize_svg(content: str) -> tuple[str, int, int]:
    """Optimiza el SVG usando Scour.

    Returns:
        (contenido_optimizado, bytes_original, bytes_nuevo)

    Raises:
        ImportError: si Scour no está instalado
    """
    from scour import scour as scour_lib  # import tardío para error claro

    options = scour_lib.sanitizeOptions(scour_lib.parse_args([
        "--enable-viewboxing",
        "--enable-id-stripping",
        "--enable-comment-stripping",
        "--shorten-ids",
        "--indent=space",
    ]))
    # Preservar ids semánticos (no acortar los que empiecen con prefijos conocidos)
    options.protect_ids_noninkscape = True

    original_bytes = len(content.encode("utf-8"))
    optimized = scour_lib.scourString(content, options)
    new_bytes = len(optimized.encode("utf-8"))

    return optimized, original_bytes, new_bytes


# ── análisis de elementos ─────────────────────────────────────────────────────

def extract_svg_elements(svg_content: str) -> list[dict]:
    """Extrae elementos con id del SVG para describe_figure()."""
    clean = re.sub(r'\s+xmlns(?::[a-z]+)?="[^"]*"', "", svg_content)
    clean = re.sub(r"<(/?)([a-z]+):", r"<\1", clean)

    try:
        root = ET.fromstring(clean)
    except ET.ParseError:
        return []

    results: list[dict] = []
    _collect(root, results, depth=0)
    return results


def _collect(elem: ET.Element, results: list, depth: int):
    tag = _tag_name(elem)
    elem_id = elem.get("id", "")

    skip_prefixes = ("defs", "marker", "linearGradient", "radialGradient", "pattern")
    if elem_id and not any(elem_id.startswith(p) for p in skip_prefixes):
        results.append({
            "tag": tag,
            "id": elem_id,
            "description": _describe(elem, tag),
            "depth": depth,
        })

    for child in elem:
        _collect(child, results, depth + 1)


def _tag_name(elem: ET.Element) -> str:
    tag = elem.tag
    return tag.split("}")[-1] if "}" in tag else tag


def _describe(elem: ET.Element, tag: str) -> str:
    text = (elem.text or "").strip()
    if text:
        return f'"{text}"'

    for child in elem:
        child_text = (child.text or "").strip()
        if child_text:
            return f'"{child_text}"'

    descriptions = {
        "rect":     lambda e: f"Rectángulo {e.get('width','?')}×{e.get('height','?')}px",
        "circle":   lambda e: f"Círculo r={e.get('r','?')}px",
        "ellipse":  lambda e: f"Elipse rx={e.get('rx','?')} ry={e.get('ry','?')}",
        "path":     lambda _: "Trayectoria (path)",
        "line":     lambda e: (
            f"Línea ({e.get('x1','?')},{e.get('y1','?')}) → "
            f"({e.get('x2','?')},{e.get('y2','?')})"
        ),
        "polyline": lambda _: "Polilínea",
        "polygon":  lambda _: "Polígono",
        "text":     lambda _: "Texto",
        "g":        lambda e: f"Grupo ({sum(1 for _ in e)} hijos)",
        "image":    lambda e: f"Imagen {e.get('width','?')}×{e.get('height','?')}px",
    }

    fn = descriptions.get(tag)
    return fn(elem) if fn else tag
