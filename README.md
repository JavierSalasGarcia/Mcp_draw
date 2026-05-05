# MCP Draw

Convierte bocetos de figuras técnicas en vectores SVG profesionales editables en Inkscape, mediante instrucciones en lenguaje natural.

Diseñado para tesistas de ingeniería (electrónica, computación, IA) que necesitan figuras de calidad para publicaciones científicas sin experiencia previa en ilustración.

---

## ¿Por qué un MCP y no simplemente pedirle a Claude que haga el SVG?

Es una pregunta válida: Claude puede generar código SVG directamente en el chat sin ninguna instalación. Entonces, ¿qué cambia al usar este MCP?

### Lo que pasa cuando le pides a Claude un SVG en el chat

1. Claude escribe el código SVG como texto en la conversación
2. Tú copias ese texto, abres un editor de texto, lo pegas y guardas el archivo como `figura.svg`
3. Abres Inkscape manualmente y cargas el archivo
4. Si quieres un cambio, vuelves al chat, pegas el SVG completo, describes el cambio, copias la respuesta, vuelves al archivo, lo reemplazas, guardas, y recargas Inkscape
5. Si la figura es compleja, el SVG puede tener 200-400 líneas — todo eso ocupa espacio en la conversación y hace que el historial se vuelva lento e inmanejable

Funciona, pero el ciclo de edición es completamente manual y se vuelve tedioso rápidamente.

### Lo que hace diferente este MCP

El MCP le da a Claude acceso directo al sistema de archivos y a Inkscape. Esto cambia el flujo de tres formas concretas:

**1. Lee tu boceto como archivo, no como descripción**
Con el chat, tienes que describir con palabras lo que dibujaste, o pegar la imagen. Con el MCP, Claude abre directamente la foto de tu boceto desde tu disco y la analiza junto con el pie de figura. El resultado es más fiel a lo que quisiste dibujar porque Claude ve exactamente lo que trazaste.

**2. La edición es un ciclo directo, sin copiar y pegar**
Cuando dices "cambia el bloque clasificador a azul", el MCP escribe el cambio al archivo SVG en disco e Inkscape se recarga automáticamente. Tú ves el resultado en segundos. En el chat, ese mismo cambio requiere que copies el SVG actual, lo pegues en la conversación, esperes la respuesta, copies la respuesta y la pegues de vuelta en el archivo.

**3. La figura existe fuera de la conversación**
En el chat, el SVG vive en el historial de mensajes. Si empiezas una nueva conversación, perdiste el contexto. Con el MCP, el archivo está en tu disco (`~/mcp_draw_figures/`), Inkscape lo tiene abierto, y el MCP sabe cuál es la figura activa aunque reinicies la sesión — solo le das la ruta del archivo y retoma desde ahí.

### Resumen comparativo

| | Claude en el chat | MCP Draw |
|---|---|---|
| Entrada | Descripción de texto o imagen pegada | Foto del boceto leída directamente del disco |
| Guardar el SVG | Manual (copiar y pegar) | Automático |
| Abrir en Inkscape | Manual | Automático |
| Editar | Copiar SVG → chat → copiar respuesta → reemplazar archivo | Escribir instrucción → Inkscape se recarga |
| Historial de chat | Se llena con código SVG | Solo contiene instrucciones y confirmaciones |
| Persistencia entre sesiones | Ninguna | El archivo queda en disco |
| Exportar a PDF/PNG | Manual desde Inkscape | Un comando desde el chat |
| Claude "ve" el resultado | Solo si tú le pegas una captura | Sí: `render_preview()` entrega el PNG renderizado directamente a Claude |

En síntesis: pedirle a Claude un SVG en el chat es como pedirle a alguien que te dicte el código de tu figura por teléfono. El MCP es como tener a esa persona sentada frente a la computadora, con acceso a tus archivos y a Inkscape, haciendo los cambios directamente mientras tú observas — y además puede abrir sus propios ojos para verificar que el resultado se ve bien.

---

## ¿Qué hace?

| Herramienta | Descripción |
|---|---|
| `create_figure` | Toma una foto de un boceto + el pie de figura y genera un SVG estilo IEEE |
| `render_preview` | Renderiza el SVG a PNG para que Claude pueda verlo visualmente y detectar problemas |
| `edit_figure` | Modifica la figura con instrucciones en español o inglés |
| `validate_figure` | Verifica la sintaxis XML y la estructura semántica del SVG |
| `optimize_figure` | Limpia el SVG con Scour para reducir su tamaño antes de entregar |
| `export_figure` | Exporta a PDF, PNG, SVG o EPS para incluir en el artículo |
| `describe_figure` | Lista los elementos de la figura con sus IDs para facilitar ediciones |

**Tipos de figura soportados:** diagramas de bloques, diagramas de flujo, grafos.

---

## Requisitos

- Windows 10/11
- [Python 3.11+](https://www.python.org/downloads/)
- [Inkscape 1.x](https://inkscape.org/release/) instalado en `C:\Program Files\Inkscape\`
- [VS Code](https://code.visualstudio.com/) con la extensión [Claude Code](https://marketplace.visualstudio.com/items?itemName=Anthropic.claude-code)
- API key de Anthropic ([obtener aquí](https://console.anthropic.com/))

---

## Instalación

### 1. Clonar el repositorio

```
git clone https://github.com/javiersalasgarcia/mcp_draw.git
cd mcp_draw
```

### 2. Crear entorno virtual e instalar dependencias

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar la API key de Anthropic

En Windows, agregar la variable de entorno de forma permanente:

```
setx ANTHROPIC_API_KEY "sk-ant-..."
```

Cierra y vuelve a abrir la terminal para que el cambio tenga efecto.

### 4. Configurar el MCP en VS Code

El archivo `.mcp.json` ya está incluido en el repositorio. Claude Code lo detecta automáticamente al abrir la carpeta del proyecto en VS Code.

Si prefieres configurarlo manualmente, abre VS Code y agrega esto en tu `settings.json` de usuario:

```json
{
  "claude.mcpServers": {
    "mcp-draw": {
      "command": "python",
      "args": ["C:\\ruta\\al\\proyecto\\mcp_draw\\server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "${env:ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

### 5. Verificar la instalación

En la terminal de VS Code:

```
python server.py
```

Deberías ver: `Starting MCP server mcp-draw...`

---

## Uso

Abre el chat de Claude Code en VS Code (`Ctrl+Shift+P` → `Claude: Open Chat`) y escribe:

### Crear una figura desde un boceto

```
Tengo el boceto de un diagrama de bloques en C:\Users\yo\bocetos\figura1.jpg
El pie de figura es: "Arquitectura del sistema de clasificación propuesto"
Usa create_figure para generar la figura.
```

### Verificar visualmente el resultado (Claude lo ve y comenta)

```
Muéstrame cómo quedó la figura con render_preview
```

### Editar la figura

```
Cambia el color del bloque "Clasificador" a azul oscuro y agranda la fuente a 16px
```

```
Añade una flecha de retroalimentación desde el bloque de salida al bloque de entrada
```

```
Agrega un nuevo bloque llamado "Normalización" entre la entrada y el clasificador
```

### Validar antes de entregar

```
Valida la figura actual
```

### Optimizar y exportar

```
Optimiza la figura y luego expórtala a PDF
```

### Ver los elementos de la figura

```
Describe los elementos de la figura actual
```

---

## Flujo de trabajo típico

```
1. El tesista hace un boceto a mano (papel o tablet)
2. Toma una foto o captura de pantalla del boceto
3. En VS Code, le pide a Claude que genere la figura con create_figure()
4. Inkscape se abre automáticamente con el SVG generado
5. Claude llama a render_preview() y VE el resultado visualmente
6. Si hay problemas, Claude los detecta y sugiere correcciones con edit_figure()
7. El tesista itera con instrucciones en lenguaje natural hasta quedar conforme
8. Antes de entregar, optimize_figure() limpia el SVG
9. export_figure() genera el PDF/PNG listo para el artículo
```

---

## Lo que se incorporó de SVG-MCP

Este proyecto integra ideas del [SVG-MCP de adamryczkowski](https://github.com/adamryczkowski/SVG-MCP),
adaptadas para el caso de uso de figuras científicas:

| Idea de SVG-MCP | Cómo se adaptó en MCP Draw |
|---|---|
| `svg_render` → PNG para visión | `render_preview()`: renderiza con Inkscape (mayor fidelidad que CairoSVG) y devuelve la imagen directamente a Claude para inspección |
| `svg_validate` con reporte de errores | `validate_figure()`: valida XML + verifica estructura semántica (viewBox, ids de bloques/flechas, marcadores) |
| `svg_optimize` vía Scour | `optimize_figure()`: usa Scour con opciones ajustadas para preservar ids semánticos que usa edit_figure() |
| `svg_diff` (comparación visual) | Pendiente para versión futura |

La diferencia principal es que SVG-MCP es un validador/renderizador genérico, mientras que MCP Draw
está especializado en figuras científicas: genera desde bocetos con visión, mantiene estilo IEEE,
usa ids semánticos para edición precisa, y controla Inkscape para el flujo editorial completo.

---

## Dónde se guardan los archivos

Las figuras se guardan en `C:\Users\[tu-usuario]\mcp_draw_figures\` con nombres como `figura_20241201_143022.svg`.

---

## Solución de problemas

**"ANTHROPIC_API_KEY no configurada"**
Verifica que la variable de entorno esté definida: `echo %ANTHROPIC_API_KEY%`

**"Inkscape no encontrado"**
Verifica que Inkscape esté instalado en `C:\Program Files\Inkscape\bin\inkscape.exe`.
Si lo instalaste en otra ruta, edita `inkscape_controller.py` y agrega tu ruta a `_INKSCAPE_WINDOWS`.

**El SVG se genera pero Inkscape no se abre**
El SVG fue guardado igualmente. Ábrelo manualmente desde Inkscape con `Archivo → Abrir`.

**Error de importación de módulos**
Asegúrate de activar el entorno virtual: `.venv\Scripts\activate`
