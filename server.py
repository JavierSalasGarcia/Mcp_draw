#!/usr/bin/env python3
"""
MCP Draw - Generador y editor de figuras científicas vectoriales
Para editores y tesistas de ingeniería: convierte bocetos en figuras
IEEE-style editables en Inkscape mediante instrucciones en lenguaje natural.
"""

import os
import base64
import mimetypes
from pathlib import Path
from datetime import datetime

import anthropic
from mcp.server.fastmcp import FastMCP, Image

from inkscape_controller import InkscapeController
from svg_utils import (
    clean_svg_response,
    extract_svg_elements,
    render_svg_to_png,
    validate_svg_detailed,
    optimize_svg,
)

# ── servidor MCP ─────────────────────────────────────────────────────────────

mcp = FastMCP(
    "mcp-draw",
    description=(
        "Convierte bocetos de figuras técnicas en vectores SVG editables en Inkscape. "
        "Soporta diagramas de bloques, diagramas de flujo y grafos para publicaciones científicas."
    ),
)

# ── estado de sesión ──────────────────────────────────────────────────────────

_output_dir = Path.home() / "mcp_draw_figures"
_output_dir.mkdir(exist_ok=True)

_session = {
    "current_svg": None,
    "inkscape": InkscapeController(),
}

# ── prompts ───────────────────────────────────────────────────────────────────

_PROMPT_CREAR = """\
Eres un experto en ilustración científica especializado en figuras estilo IEEE \
para publicaciones de ingeniería y tesis académicas.

Se te proporciona:
1. Un boceto (puede ser un dibujo a mano, esquema rugoso o foto de papel)
2. El pie de figura que describe lo que debe mostrar

Tu tarea: generar un SVG profesional, limpio y editable.

Pie de figura: {caption}
Tipo de figura: {figure_type}

═══ REQUISITOS OBLIGATORIOS ═══

ESTRUCTURA SVG:
• viewBox="0 0 800 600" — ajusta la altura si el contenido lo requiere
• Todo elemento visible DEBE tener un id semántico y descriptivo:
    - Bloques/cajas:       id="block-[nombre]"           ej. id="block-clasificador"
    - Flechas/conectores:  id="arrow-[origen]-[destino]" ej. id="arrow-entrada-clasificador"
    - Etiquetas de texto:  id="label-[nombre]"           ej. id="label-precision"
    - Decisiones (rombos): id="decision-[condicion]"     ej. id="decision-umbral"
    - Nodos de grafo:      id="node-[nombre]"            ej. id="node-sensor1"
• Agrupa elementos relacionados con <g id="layer-bloques">, <g id="layer-flechas">, etc.
• Define flechas reutilizables con <defs><marker>

ESTILO (IEEE Publication Style):
• Fuente:               font-family="Arial, Helvetica, sans-serif"
• Bloques rectangulares: fill="#EBF4FA" stroke="#2C5F8A" stroke-width="1.5"
• Bloques proceso:       fill="#F5F5F5" stroke="#333333" stroke-width="1.5"
• Rombos de decisión:    fill="#FFF9E6" stroke="#8B6914" stroke-width="1.5"
• Nodos inicio/fin:      fill="#D5E8D4" stroke="#82B366" stroke-width="1.5" rx="20"
• Flechas:               stroke="#333333" stroke-width="1.5" fill="none"
• Texto principal:       font-size="14" fill="#1A1A1A"
• Texto secundario:      font-size="12" fill="#444444"
• Separación mínima entre elementos: 50px

TIPOS DE FIGURA:
• block_diagram — Bloques rectangulares con flechas, flujo izquierda→derecha o arriba→abajo
• flowchart     — Procesos (rect), decisiones (rombo), inicio/fin (rect redondeado)
• graph         — Nodos (círculos) con aristas etiquetadas
• auto          — Infiere el tipo a partir del boceto y el pie de figura

SALIDA:
Devuelve ÚNICAMENTE el código SVG válido y completo. Sin markdown, sin explicaciones.
"""

_PROMPT_EDITAR = """\
Eres un editor de figuras SVG científicas. Aplica exactamente el cambio solicitado.

SVG actual:
{current_svg}

Instrucción: {instruction}

REGLAS:
1. Devuelve ÚNICAMENTE el SVG completo modificado — sin markdown ni explicaciones
2. Aplica EXACTAMENTE el cambio pedido, sin modificar nada más
3. Conserva todos los id existentes
4. Mantén el viewBox y dimensiones originales salvo que se pida cambiarlos
5. Si añades un elemento nuevo, dale un id semántico siguiendo la convención existente
6. Mantén el mismo estilo visual y calidad profesional

SVG modificado:
"""

_PROMPT_VERIFICAR = """\
Acabas de generar o editar esta figura SVG. Obsérvala visualmente y evalúa:

1. ¿Los elementos están bien posicionados y no se superponen?
2. ¿Las flechas conectan correctamente los bloques/nodos?
3. ¿El texto es legible y está centrado dentro de sus elementos?
4. ¿El estilo es consistente y apropiado para una publicación científica?
5. ¿La figura refleja fielmente lo que describe el pie: "{caption}"?

Si detectas algún problema, descríbelo con precisión para poder corregirlo \
con edit_figure(). Si todo se ve bien, confírmalo brevemente.
"""


# ── utilidades internas ───────────────────────────────────────────────────────

def _client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "Variable de entorno ANTHROPIC_API_KEY no configurada. "
            "Agrégala en la configuración del MCP en VS Code."
        )
    return anthropic.Anthropic(api_key=key)


def _encode_image(path: str) -> tuple[str, str]:
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Imagen no encontrada: {path}")
    media_type = mimetypes.guess_type(str(resolved))[0] or "image/jpeg"
    data = base64.standard_b64encode(resolved.read_bytes()).decode()
    return data, media_type


def _svg_path(name: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _output_dir / f"{name}_{ts}.svg"


# ── herramientas MCP ──────────────────────────────────────────────────────────

@mcp.tool()
def create_figure(
    sketch_path: str,
    caption: str,
    figure_type: str = "auto",
) -> str:
    """Crea una figura vectorial profesional a partir de un boceto.

    Analiza la imagen del boceto junto con el pie de figura para generar
    un SVG limpio estilo IEEE, listo para editar en Inkscape.

    Args:
        sketch_path: Ruta completa a la imagen del boceto (JPG, PNG)
        caption: Pie de figura que describe qué debe mostrar la imagen
        figure_type: 'block_diagram', 'flowchart', 'graph' o 'auto' (por defecto)

    Returns:
        Ruta al SVG generado. Usa render_preview() para verificar el resultado visualmente.
    """
    image_data, media_type = _encode_image(sketch_path)
    client = _client()

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8192,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": _PROMPT_CREAR.format(
                            caption=caption,
                            figure_type=figure_type,
                        ),
                    },
                ],
            }
        ],
    )

    svg = clean_svg_response(response.content[0].text)
    out = _svg_path("figura")
    out.write_text(svg, encoding="utf-8")
    _session["current_svg"] = str(out)
    _session["caption"] = caption

    inkscape_msg = _session["inkscape"].open_file(str(out))

    return (
        f"Figura creada.\n"
        f"SVG: {out}\n"
        f"Inkscape: {inkscape_msg}\n\n"
        f"Usa render_preview() para que pueda ver cómo quedó y verificar que "
        f"el resultado es correcto antes de hacer ajustes."
    )


@mcp.tool()
def render_preview(svg_path: str = None, width: int = 900) -> Image:
    """Renderiza la figura a PNG para inspección visual.

    Permite a Claude ver cómo se ve realmente la figura generada o editada,
    cerrando el ciclo de retroalimentación visual. Úsalo después de
    create_figure() o edit_figure() para verificar el resultado.

    Args:
        svg_path: SVG a renderizar (usa la figura actual si se omite)
        width: Ancho del PNG en píxeles (por defecto 900)

    Returns:
        Imagen PNG de la figura para inspección visual
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        raise ValueError(
            "No hay ninguna figura abierta. Usa create_figure() primero."
        )

    preview_path = str(Path(target).with_suffix(".preview.png"))
    error = render_svg_to_png(
        svg_path=target,
        output_path=preview_path,
        width=width,
        inkscape_exe=_session["inkscape"]._exe,
    )

    if error:
        raise RuntimeError(
            f"No se pudo renderizar la figura: {error}\n"
            f"Verifica que Inkscape esté instalado correctamente."
        )

    return Image(data=Path(preview_path).read_bytes(), format="png")


@mcp.tool()
def edit_figure(instruction: str, svg_path: str = None) -> str:
    """Edita la figura actual con una instrucción en lenguaje natural.

    Después de editar, usa render_preview() para verificar visualmente que
    el cambio quedó como se esperaba.

    Ejemplos:
    - "Cambia el color del bloque clasificador a azul oscuro"
    - "Agrega una flecha de retroalimentación del bloque salida al de entrada"
    - "Añade un nuevo bloque llamado Post-procesamiento después del clasificador"
    - "Aumenta el tamaño de fuente de todas las etiquetas a 16px"

    Args:
        instruction: Qué cambiar, en español o inglés
        svg_path: SVG a editar (usa la figura actual si se omite)

    Returns:
        Confirmación del cambio. Sigue con render_preview() para verificar.
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        return (
            "No hay ninguna figura abierta. "
            "Usa create_figure() primero."
        )

    current_svg = Path(target).read_text(encoding="utf-8")
    client = _client()

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8192,
        messages=[
            {
                "role": "user",
                "content": _PROMPT_EDITAR.format(
                    current_svg=current_svg,
                    instruction=instruction,
                ),
            }
        ],
    )

    svg = clean_svg_response(response.content[0].text)
    Path(target).write_text(svg, encoding="utf-8")
    _session["current_svg"] = target

    reload_msg = _session["inkscape"].reload_file(target)

    return (
        f"Figura actualizada.\n"
        f"Inkscape: {reload_msg}\n\n"
        f"Usa render_preview() para verificar visualmente el cambio."
    )


@mcp.tool()
def validate_figure(svg_path: str = None) -> str:
    """Valida la sintaxis y estructura del SVG de la figura actual.

    Detecta errores de XML, elementos sin id semántico, ausencia de viewBox,
    y otros problemas que podrían causar que la figura no se vea bien en
    Inkscape o en la publicación final.

    Args:
        svg_path: SVG a validar (usa la figura actual si se omite)

    Returns:
        Reporte de validación con errores y advertencias
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        return "No hay ninguna figura abierta. Usa create_figure() primero."

    content = Path(target).read_text(encoding="utf-8")
    report = validate_svg_detailed(content)
    return f"Validación de: {target}\n\n{report}"


@mcp.tool()
def optimize_figure(svg_path: str = None) -> str:
    """Optimiza el SVG para entrega en revista científica.

    Usa Scour para limpiar el SVG: elimina metadatos innecesarios, comentarios,
    definiciones sin usar y simplifica el código. Reduce el tamaño del archivo
    sin cambiar el aspecto visual. Ideal antes de entregar la figura final.

    Args:
        svg_path: SVG a optimizar (usa la figura actual si se omite)

    Returns:
        Reporte de optimización con reducción de tamaño
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        return "No hay ninguna figura abierta. Usa create_figure() primero."

    content = Path(target).read_text(encoding="utf-8")

    try:
        optimized, original_bytes, new_bytes = optimize_svg(content)
    except ImportError:
        return (
            "Scour no está instalado. Ejecuta:\n"
            "  pip install scour\n"
            "y vuelve a intentarlo."
        )

    Path(target).write_text(optimized, encoding="utf-8")
    reduction = round((1 - new_bytes / original_bytes) * 100, 1)

    return (
        f"SVG optimizado.\n"
        f"Tamaño original: {original_bytes:,} bytes\n"
        f"Tamaño nuevo:    {new_bytes:,} bytes\n"
        f"Reducción:       {reduction}%\n"
        f"Archivo:         {target}"
    )


@mcp.tool()
def export_figure(
    format: str = "pdf",
    output_path: str = None,
    svg_path: str = None,
) -> str:
    """Exporta la figura a PDF, PNG o SVG para incluir en el artículo.

    Se recomienda optimizar con optimize_figure() antes de exportar.

    Args:
        format: 'pdf', 'png', 'svg' o 'eps' (por defecto: 'pdf')
        output_path: Dónde guardar (por defecto: misma carpeta que el SVG)
        svg_path: SVG a exportar (usa la figura actual si se omite)

    Returns:
        Ruta al archivo exportado
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        return "No hay ninguna figura abierta. Usa create_figure() primero."

    svg_p = Path(target)
    dest = output_path or str(svg_p.with_suffix(f".{format}"))

    return _session["inkscape"].export_file(target, dest, format)


@mcp.tool()
def describe_figure(svg_path: str = None) -> str:
    """Describe los elementos de la figura con sus IDs.

    Útil para conocer qué elementos existen antes de pedir ediciones.
    Los IDs listados pueden usarse en instrucciones de edit_figure().

    Args:
        svg_path: SVG a describir (usa la figura actual si se omite)

    Returns:
        Lista de elementos con IDs y descripción
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        return "No hay ninguna figura abierta. Usa create_figure() primero."

    svg_content = Path(target).read_text(encoding="utf-8")
    elements = extract_svg_elements(svg_content)

    if not elements:
        return "No se pudieron analizar los elementos de la figura."

    lines = [f"Figura: {target}", f"Elementos con id ({len(elements)}):", ""]
    for e in elements:
        indent = "  " * min(e["depth"], 3)
        lines.append(f"{indent}• <{e['tag']}> id=\"{e['id']}\" — {e['description']}")

    return "\n".join(lines)


# ── entrada ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
