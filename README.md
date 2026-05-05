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
| `create_figure` | Toma foto de boceto + pie de figura → genera SVG estilo IEEE → guarda v1 automáticamente |
| `render_preview` | Renderiza el SVG a PNG para que Claude pueda verlo visualmente y detectar problemas |
| `edit_figure` | Modifica la figura con instrucciones en español o inglés → guarda versión de respaldo antes de editar |
| `list_versions` | Muestra el historial completo de versiones con timestamps y descripción de cada cambio |
| `restore_version` | Restaura la figura a cualquier versión anterior (guarda el estado actual antes de restaurar) |
| `diff_versions` | Compara dos versiones visualmente lado a lado en una imagen |
| `gallery_versions` | Muestra todas las versiones como galería de miniaturas en una sola imagen |
| `merge_versions` | Combina características de dos versiones según instrucción en lenguaje natural |
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

**Dependencias Python** (se instalan con `pip install -r requirements.txt`):

| Paquete | Para qué se usa |
|---|---|
| `mcp` | Protocolo MCP (servidor) |
| `anthropic` | API de Claude para visión y generación de SVG |
| `scour` | Optimización del SVG antes de entregar |
| `Pillow` | Imagen comparativa lado a lado en `diff_versions()` |

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

### Ver el historial de versiones

```
Muéstrame todas las versiones guardadas de la figura
```

### Comparar dos versiones (svg_diff)

```
Compara la versión 2 con la versión 5
```

```
Muéstrame cómo quedó la figura antes y después del último cambio
```

### Volver a una versión anterior

```
La figura quedó rota, regresa a la versión 3
```

```
Restaura la versión anterior de la figura
```

### Ver la galería de todas las versiones

```
Muéstrame la galería de versiones
```

### Mezclar características de dos versiones

```
Usa la estructura de la versión 3 pero los colores de la versión 5
```

```
merge_versions(2, 6, "conserva las flechas y conectores de la v2, pero aplica la paleta de colores de la v6")
```

```
Toma el layout de la v1 pero usa las etiquetas y texto de la v4
```

> El estudiante primero ve la galería para identificar qué versiones tiene,
> luego pide la mezcla que prefiere. Claude lee ambos SVGs y produce
> una versión híbrida que se guarda automáticamente en el historial.

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
1.  El tesista hace un boceto a mano (papel o tablet)
2.  Toma una foto o captura de pantalla del boceto
3.  En VS Code, le pide a Claude que genere la figura con create_figure()
     → Se guarda automáticamente como v1
4.  Inkscape se abre automáticamente con el SVG generado
5.  Claude llama a render_preview() y VE el resultado visualmente
6.  Si hay problemas, Claude los detecta y corrige con edit_figure()
     → Antes de cada edición se guarda una versión de respaldo automáticamente
7.  El tesista puede ver el historial con list_versions()
8.  Si un cambio rompe la figura, restore_version(N) la devuelve al estado anterior
9.  Para comparar cómo estaba antes y después: diff_versions(N, M)
10. Antes de entregar: optimize_figure() limpia el SVG
11. export_figure() genera el PDF/PNG listo para el artículo
```

### Dónde se guardan las versiones

```
~/mcp_draw_figures/
├── figura_20241201_143022.svg          ← archivo activo
├── figura_20241201_143022.preview.png  ← última vista previa
└── .versions/
    └── figura_20241201_143022/
        ├── v001.svg  ← "Figura inicial generada desde boceto"
        ├── v002.svg  ← "auto: Cambia el bloque clasificador a azul"
        ├── v003.svg  ← "auto: Añade flecha de retroalimentación"
        └── history.json
```

Las versiones nunca se borran automáticamente. Cada vez que se restaura una versión
o se aplica una mezcla, el estado actual se guarda primero — ningún trabajo se pierde.

### Flujo de trabajo con galería y mezcla

```
gallery_versions()           → ver todas las versiones en una imagen
       ↓
diff_versions(3, 5)          → comparar dos candidatas lado a lado
       ↓
merge_versions(3, 5,         → crear versión híbrida
  "estructura de v3,
   colores de v5")
       ↓
render_preview()             → Claude verifica que la mezcla quedó bien
       ↓
optimize_figure()  →  export_figure()
```

---

## Lo que se incorporó de SVG-MCP

Este proyecto integra ideas del [SVG-MCP de adamryczkowski](https://github.com/adamryczkowski/SVG-MCP),
adaptadas para el caso de uso de figuras científicas:

| Idea de SVG-MCP | Cómo se adaptó en MCP Draw |
|---|---|
| `svg_render` → PNG para visión | `render_preview()`: renderiza con Inkscape y devuelve la imagen directamente a Claude para inspección |
| `svg_validate` con reporte de errores | `validate_figure()`: valida XML + estructura semántica (viewBox, ids, marcadores) |
| `svg_optimize` vía Scour | `optimize_figure()`: Scour con opciones que preservan los ids semánticos que usa edit_figure() |
| `svg_diff` comparación visual | `diff_versions()`: compara cualquier par de versiones del historial, imagen lado a lado generada con Pillow |

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
