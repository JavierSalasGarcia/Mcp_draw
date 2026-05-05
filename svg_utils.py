"""
Utilidades para procesamiento y análisis de SVG.
"""

import re
from xml.etree import ElementTree as ET


def clean_svg_response(text: str) -> str:
    """Extrae SVG limpio de una respuesta de Claude.

    Claude a veces envuelve el SVG en bloques markdown (```svg ... ```).
    Esta función extrae solo el contenido SVG válido.
    """
    text = text.strip()

    # Eliminar bloque de código markdown si existe
    if text.startswith("```"):
        lines = text.splitlines()
        # Quitar primera línea (```svg o ```) y última (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()

    # Encontrar el inicio real del SVG por si hay texto antes
    svg_start = text.find("<svg")
    if svg_start > 0:
        text = text[svg_start:]

    return text


def validate_svg(content: str) -> tuple[bool, str]:
    """Valida que el contenido sea SVG bien formado.

    Returns:
        (es_válido, mensaje)
    """
    if not content.strip().startswith("<"):
        return False, "El contenido no comienza con una etiqueta XML"
    if "<svg" not in content:
        return False, "No se encontró elemento <svg>"
    try:
        ET.fromstring(content)
        return True, "SVG válido"
    except ET.ParseError as e:
        return False, f"Error de parseo XML: {e}"


def extract_svg_elements(svg_content: str) -> list[dict]:
    """Extrae elementos con id del SVG para describe_figure().

    Returns:
        Lista de dicts con keys: tag, id, description, depth
    """
    # Eliminar declaraciones de namespace para simplificar el parsing
    clean = re.sub(r'\s+xmlns(?::[a-z]+)?="[^"]*"', "", svg_content)
    # Eliminar prefijos de namespace en nombres de etiquetas
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

    # Incluir solo elementos con id significativo (excluir defs y markers internos)
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
    """Genera una descripción breve del elemento."""
    # Si tiene texto visible, usarlo
    text = (elem.text or "").strip()
    if text:
        return f'"{text}"'

    # Buscar texto en hijos directos
    for child in elem:
        child_text = (child.text or "").strip()
        if child_text:
            return f'"{child_text}"'

    # Descripción por tipo de elemento
    descriptions = {
        "rect": lambda e: f"Rectángulo {e.get('width','?')}×{e.get('height','?')}px",
        "circle": lambda e: f"Círculo r={e.get('r','?')}px",
        "ellipse": lambda e: f"Elipse rx={e.get('rx','?')} ry={e.get('ry','?')}",
        "path": lambda _: "Trayectoria (path)",
        "line": lambda e: f"Línea de ({e.get('x1','?')},{e.get('y1','?')}) a ({e.get('x2','?')},{e.get('y2','?')})",
        "polyline": lambda _: "Polilínea",
        "polygon": lambda _: "Polígono",
        "text": lambda _: "Elemento de texto",
        "g": lambda e: f"Grupo ({sum(1 for _ in e)} hijos)",
        "image": lambda e: f"Imagen {e.get('width','?')}×{e.get('height','?')}px",
    }

    fn = descriptions.get(tag)
    return fn(elem) if fn else tag
