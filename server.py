#!/usr/bin/env python3
"""
MCP Draw - Generador y editor de figuras científicas vectoriales
Para editores y tesistas de ingeniería: convierte bocetos en figuras
IEEE-style editables en Inkscape mediante instrucciones en lenguaje natural.
"""

import io
import os
import base64
import mimetypes
from pathlib import Path
from datetime import datetime

import anthropic
from mcp.server.fastmcp import FastMCP, Image

from inkscape_controller import InkscapeController
from version_manager import VersionManager
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

_session: dict = {
    "current_svg": None,
    "caption": "",
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
• Fuente:                font-family="Arial, Helvetica, sans-serif"
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


def _vm(target: str) -> VersionManager:
    return VersionManager(target)


def _render_to_tmp(version_path: Path, suffix: str, width: int) -> Path:
    """Renderiza un SVG a un PNG temporal y retorna su Path."""
    out = version_path.parent / f"_diff_{suffix}.png"
    err = render_svg_to_png(
        str(version_path), str(out), width, _session["inkscape"]._exe
    )
    if err:
        raise RuntimeError(f"Error al renderizar {version_path.name}: {err}")
    return out


def _side_by_side_image(
    png_a: Path,
    png_b: Path,
    label_a: str,
    label_b: str,
) -> bytes:
    """Crea una imagen de comparación lado a lado con Pillow."""
    from PIL import Image as PILImage, ImageDraw, ImageFont

    img_a = PILImage.open(png_a).convert("RGB")
    img_b = PILImage.open(png_b).convert("RGB")

    # Altura uniforme (la mayor)
    h = max(img_a.height, img_b.height)
    if img_a.height < h:
        bg = PILImage.new("RGB", (img_a.width, h), (255, 255, 255))
        bg.paste(img_a, (0, 0))
        img_a = bg
    if img_b.height < h:
        bg = PILImage.new("RGB", (img_b.width, h), (255, 255, 255))
        bg.paste(img_b, (0, 0))
        img_b = bg

    GAP = 8
    LABEL_H = 36
    total_w = img_a.width + GAP + img_b.width
    canvas = PILImage.new("RGB", (total_w, h + LABEL_H), (220, 220, 220))
    draw = ImageDraw.Draw(canvas)

    # Etiquetas de color
    draw.rectangle([0, 0, img_a.width, LABEL_H], fill=(52, 120, 190))
    draw.rectangle([img_a.width + GAP, 0, total_w, LABEL_H], fill=(46, 160, 95))

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except (IOError, OSError):
        font = ImageFont.load_default()

    draw.text((10, 10), label_a[:55], fill="white", font=font)
    draw.text((img_a.width + GAP + 10, 10), label_b[:55], fill="white", font=font)

    canvas.paste(img_a, (0, LABEL_H))
    canvas.paste(img_b, (img_a.width + GAP, LABEL_H))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


# ── herramientas MCP ──────────────────────────────────────────────────────────

@mcp.tool()
def create_figure(
    sketch_path: str,
    caption: str,
    figure_type: str = "auto",
) -> str:
    """Crea una figura vectorial profesional a partir de un boceto.

    Analiza la imagen del boceto junto con el pie de figura para generar
    un SVG limpio estilo IEEE. Guarda automáticamente la versión inicial (v1).

    Args:
        sketch_path: Ruta completa a la imagen del boceto (JPG, PNG)
        caption: Pie de figura que describe qué debe mostrar la imagen
        figure_type: 'block_diagram', 'flowchart', 'graph' o 'auto' (por defecto)

    Returns:
        Ruta al SVG generado. Usa render_preview() para verificar visualmente.
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

    # Versión inicial
    vm = _vm(str(out))
    v_num = vm.save("Figura inicial generada desde boceto")

    inkscape_msg = _session["inkscape"].open_file(str(out))

    return (
        f"Figura creada — versión {v_num} guardada.\n"
        f"SVG: {out}\n"
        f"Inkscape: {inkscape_msg}\n\n"
        f"Usa render_preview() para verificar el resultado visualmente."
    )


@mcp.tool()
def render_preview(svg_path: str = None, width: int = 900) -> Image:
    """Renderiza la figura a PNG para inspección visual.

    Permite a Claude ver cómo se ve realmente la figura y detectar
    problemas (superposición de elementos, flechas mal conectadas, etc.)
    antes de solicitar correcciones.

    Args:
        svg_path: SVG a renderizar (usa la figura actual si se omite)
        width: Ancho del PNG en píxeles (por defecto 900)

    Returns:
        Imagen PNG de la figura para inspección visual
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        raise ValueError("No hay ninguna figura abierta. Usa create_figure() primero.")

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
            "Verifica que Inkscape esté instalado correctamente."
        )

    return Image(data=Path(preview_path).read_bytes(), format="png")


@mcp.tool()
def edit_figure(instruction: str, svg_path: str = None) -> str:
    """Edita la figura actual con una instrucción en lenguaje natural.

    Guarda automáticamente una versión de respaldo antes de aplicar
    el cambio. Si el resultado no es el esperado, usa restore_version().

    Ejemplos:
    - "Cambia el color del bloque clasificador a azul oscuro"
    - "Agrega una flecha de retroalimentación del bloque salida al de entrada"
    - "Añade un nuevo bloque llamado Post-procesamiento después del clasificador"
    - "Aumenta el tamaño de fuente de todas las etiquetas a 16px"

    Args:
        instruction: Qué cambiar, en español o inglés
        svg_path: SVG a editar (usa la figura actual si se omite)

    Returns:
        Confirmación con número de versión de respaldo creado.
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        return "No hay ninguna figura abierta. Usa create_figure() primero."

    # Guardar versión antes de editar
    vm = _vm(target)
    backup_num = vm.save(f"auto: {instruction[:80]}")

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
        f"Figura actualizada — respaldo guardado como v{backup_num}.\n"
        f"Inkscape: {reload_msg}\n\n"
        f"Usa render_preview() para verificar el cambio.\n"
        f"Si algo salió mal, usa restore_version({backup_num}) para volver atrás."
    )


@mcp.tool()
def list_versions(svg_path: str = None) -> str:
    """Lista todas las versiones guardadas de la figura actual.

    Muestra número de versión, fecha/hora, y descripción del cambio
    que originó cada versión. Útil para saber a qué versión volver
    si la figura actual tiene problemas.

    Args:
        svg_path: SVG a consultar (usa la figura actual si se omite)

    Returns:
        Historial de versiones con timestamps y comentarios
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        return "No hay ninguna figura abierta. Usa create_figure() primero."

    vm = _vm(target)
    history = vm.list()

    if not history:
        return "Esta figura no tiene versiones guardadas aún."

    lines = [
        f"Historial de versiones: {Path(target).name}",
        f"Total: {len(history)} versión(es)",
        "",
    ]
    for entry in history:
        size_kb = entry.get("size_bytes", 0) / 1024
        lines.append(
            f"  v{entry['version']:03d} | {entry['timestamp']} | "
            f"{size_kb:5.1f} KB | {entry['comment']}"
        )

    lines += [
        "",
        "Para restaurar una versión: restore_version(<número>)",
        "Para comparar dos versiones: diff_versions(<v_anterior>, <v_actual>)",
    ]
    return "\n".join(lines)


@mcp.tool()
def restore_version(version_number: int, svg_path: str = None) -> str:
    """Restaura la figura a una versión anterior.

    Guarda el estado actual como nueva versión antes de restaurar,
    por lo que ningún trabajo se pierde. Tras restaurar, Inkscape
    se recarga automáticamente con la versión anterior.

    Args:
        version_number: Número de versión a la que volver (ver list_versions())
        svg_path: SVG a restaurar (usa la figura actual si se omite)

    Returns:
        Confirmación de la restauración con números de versión
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        return "No hay ninguna figura abierta. Usa create_figure() primero."

    vm = _vm(target)

    try:
        info = vm.restore(version_number)
    except (ValueError, FileNotFoundError) as e:
        return f"No se pudo restaurar: {e}"

    reload_msg = _session["inkscape"].reload_file(target)

    return (
        f"Figura restaurada a v{info['restored_version']}.\n"
        f"  Versión restaurada: v{info['restored_version']} "
        f"({info['original_timestamp']}) — {info['original_comment']}\n"
        f"  Estado anterior guardado como: v{info['backup_version']}\n"
        f"  Versión actual: v{info['new_version']}\n"
        f"Inkscape: {reload_msg}"
    )


@mcp.tool()
def diff_versions(
    version_a: int = None,
    version_b: int = None,
    svg_path: str = None,
) -> Image:
    """Compara visualmente dos versiones de la figura lado a lado.

    Renderiza ambas versiones y las presenta en una imagen comparativa
    con etiquetas de color. Útil para verificar qué cambió entre ediciones
    o para decidir cuál versión conservar.

    Args:
        version_a: Primera versión (por defecto: la penúltima)
        version_b: Segunda versión (por defecto: la última)
        svg_path: SVG a comparar (usa la figura actual si se omite)

    Returns:
        Imagen PNG con las dos versiones lado a lado
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        raise ValueError("No hay ninguna figura abierta. Usa create_figure() primero.")

    vm = _vm(target)
    history = vm.list()

    if len(history) < 2:
        raise ValueError(
            f"Se necesitan al menos 2 versiones para comparar. "
            f"Hay {len(history)} versión(es) guardada(s)."
        )

    # Defaults: penúltima vs última
    if version_b is None:
        version_b = len(history)
    if version_a is None:
        version_a = max(1, version_b - 1)

    path_a = vm.get_path(version_a)
    path_b = vm.get_path(version_b)

    # Renderizar ambas versiones
    try:
        png_a = _render_to_tmp(path_a, f"v{version_a:03d}", width=700)
        png_b = _render_to_tmp(path_b, f"v{version_b:03d}", width=700)
    except RuntimeError as e:
        raise RuntimeError(
            f"{e}\nVerifica que Inkscape esté instalado correctamente."
        ) from e

    # Etiquetas para la comparación
    info_a = history[version_a - 1]
    info_b = history[version_b - 1]
    label_a = f"v{version_a} | {info_a['timestamp'][11:16]} — {info_a['comment']}"
    label_b = f"v{version_b} | {info_b['timestamp'][11:16]} — {info_b['comment']}"

    try:
        png_bytes = _side_by_side_image(png_a, png_b, label_a, label_b)
    except ImportError:
        raise RuntimeError(
            "Pillow no está instalado. Ejecuta: pip install Pillow\n"
            "y vuelve a intentarlo."
        )
    finally:
        png_a.unlink(missing_ok=True)
        png_b.unlink(missing_ok=True)

    return Image(data=png_bytes, format="png")


@mcp.tool()
def validate_figure(svg_path: str = None) -> str:
    """Valida la sintaxis y estructura del SVG de la figura actual.

    Detecta errores de XML, elementos sin id semántico, ausencia de viewBox,
    y otros problemas que podrían causar que la figura no se vea bien.

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

    Usa Scour para limpiar el SVG: elimina metadatos innecesarios,
    comentarios y definiciones sin usar. Guarda una versión de respaldo
    antes de optimizar.

    Args:
        svg_path: SVG a optimizar (usa la figura actual si se omite)

    Returns:
        Reporte de optimización con reducción de tamaño
    """
    target = svg_path or _session.get("current_svg")
    if not target:
        return "No hay ninguna figura abierta. Usa create_figure() primero."

    # Versión de respaldo antes de optimizar
    vm = _vm(target)
    backup_num = vm.save("Pre-optimización")

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
        f"SVG optimizado — respaldo guardado como v{backup_num}.\n"
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
    """Exporta la figura a PDF, PNG, SVG o EPS para incluir en el artículo.

    Se recomienda optimize_figure() antes de exportar.

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
