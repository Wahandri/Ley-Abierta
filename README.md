# El Vigilante - Pipeline BOE España

**Traductor ciudadano del Boletín Oficial del Estado**

## 🎯 ¿Qué es El Vigilante?

El Vigilante es un proyecto cívico que **traduce las leyes y decisiones públicas del BOE a lenguaje claro** para que cualquier persona pueda entender qué se aprueba cada día y cómo le afecta.

**No es**:
- ❌ Un cazador de corrupción sensacionalista
- ❌ Una herramienta política partidista
- ❌ Un recopilatorio de contratación pública (eso viene en Fase 3)

**Es**:
- ✅ Un traductor pedagógico: del lenguaje jurídico al lenguaje ciudadano
- ✅ Una fuente de transparencia radical pero explicada
- ✅ Un dataset público, auditable y versionado

---

## 🏗️ Arquitectura del Proyecto

Este repositorio contiene el **pipeline de datos** que:

1. **Scrape** el BOE oficial diariamente
2. **Extrae** metadatos de leyes, decretos y órdenes ministeriales
3. **Procesa** con LLM (OpenAI) para generar resúmenes ciudadanos
4. **Valida** la calidad del contenido generado
5. **Genera** índices JSON optimizados para consumir en la web

**Stack tecnológico**:
- Python 3.11+
- BeautifulSoup (scraping BOE)
- OpenAI API (GPT-4o-mini para traducción ciudadana)
- JSON Schema + Pydantic (validación)
- JSONL (almacenamiento histórico versionado)

---

## 📦 Instalación

### Requisitos

- Python 3.11 o superior
- Cuenta de OpenAI con API key (costo estimado: $5-10 USD/mes)
- Conexión a Internet

### Pasos

```bash
# 1. Clonar repo
git clone https://github.com/tu-usuario/el-vigilante-scraper.git
cd el-vigilante-scraper

# 2. Crear entorno virtual
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
nano .env  # Añade tu OPENAI_API_KEY
```

**Contenido de `.env`**:
```env
OPENAI_API_KEY=sk-tu-clave-aqui
LLM_MODEL=gpt-4o-mini
LLM_MAX_TOKENS=500
LLM_TEMPERATURE=0.3
```

---

## 🚀 Uso del Pipeline

### 1. Scraping del BOE (sin LLM)

Extrae documentos del BOE y genera metadatos básicos:

```bash
# Scrape del BOE de hoy (modo dry-run)
./boe_scraper.py --date today --dry-run

# Scrape real del BOE de hoy (guarda en JSONL)
./boe_scraper.py --date today

# Scrape de una fecha específica
./boe_scraper.py --date 2026-01-27

# Limitar a 10 documentos (para testing)
./boe_scraper.py --date today --limit 10
```

**Salida**: `data/jsonl/2026/01/boe-2026-01.jsonl`

Cada línea es un JSON con metadatos básicos (sin resumen LLM aún):
- `id`, `title_original`, `url_oficial`, `date_published`
- `type` (ley, real_decreto, orden, etc.)
- `topic_primary` (clasificación heurística)
- `impact_index` (score 0-100 calculado por heurísticas)
- `summary_plain_es`: placeholder "[Pendiente de procesar]"

---

### 2. Procesamiento con LLM (OpenAI)

**Importante**: Requiere `OPENAI_API_KEY` configurada en `.env`

```bash
# Procesar un documento de ejemplo (test)
./llm_processor.py
```

Este script genera:
- `summary_plain_es`: Resumen en lenguaje ciudadano (150-300 palabras)
- `keywords`: 5-8 palabras clave relevantes
- `affects_to`: A quién afecta (`["autónomos", "empresas", ...]`)
- `transparency_notes`: Por qué es importante que la ciudadanía lo sepa

**Integración con scraper**:

Para procesar documentos scraped con LLM, necesitas integrar `llm_processor.process_document_with_llm()` en tu flujo. En futuras versiones esto será automático, pero por ahora es un paso manual.

**Ejemplo de integración**:

```python
from llm_processor import process_document_with_llm
import json

# Leer JSONL
with open("data/jsonl/2026/01/boe-2026-01.jsonl", "r") as f:
    for line in f:
        doc = json.loads(line)
        if "[Pendiente de procesar]" in doc.get("summary_plain_es", ""):
            # Procesar con LLM
            enriched_doc = process_document_with_llm(doc)
            # Guardar/actualizar...
```

---

### 3. Validación de Calidad

Valida documentos contra el schema JSON y criterios de calidad:

```bash
# Validar un archivo JSONL
./validator.py data/jsonl/2026/01/boe-2026-01.jsonl

# Validación verbose (muestra todos los warnings)
./validator.py data/jsonl/2026/01/boe-2026-01.jsonl --verbose
```

**Salida**: Reporte con:
- % de documentos válidos (schema)
- % de documentos con calidad aceptable
- Score promedio de calidad (0-100)
- Errores por tipo
- Warnings (resúmenes demasiado cortos, tecnicismos excesivos, etc.)

---

### 4. Generación de Índices para la Web

Genera archivos JSON optimizados para consumir en la web Next.js:

```bash
# Generar latest.json (últimos 30 días)
./index_generator.py --generate-latest

# Generar topics.json (todos los documentos agrupados por tema)
./index_generator.py --generate-topics

# Generar índice mensual específico
./index_generator.py --generate-monthly 2026-01

# Generar todos los índices
./index_generator.py --all
```

**Archivos generados**:
- `data/index/latest.json`: Feed de últimos 30 días (para home de la web)
- `data/index/topics.json`: Documentos agrupados por tema
- `data/index/2026-01.json`: Índice completo del mes

---

## 📂 Estructura de Datos

```
data/
├── schema/
│   └── documento-publico-v1.schema.json    # Schema JSON formal
├── jsonl/
│   └── 2026/
│       └── 01/
│           ├── boe-2026-01.jsonl           # Histórico mes (1 JSON por línea)
│           └── boe-2026-01-metadata.json   # Stats del mes (futuro)
├── index/
│   ├── latest.json                         # Últimos 30 días (web)
│   ├── 2026-01.json                        # Índice mensual
│   └── topics.json                         # Agrupado por temas
└── cache/
    └── llm_responses/                      # Caché de respuestas LLM
```

---

## 📋 Esquema `DocumentoPublico` (v1.0)

Cada documento BOE se transforma en un registro JSON con estos campos:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | string | Identificador único (ej: `boe-2026-01-27-real-decreto-a3f2`) |
| `source` | string | Siempre `"BOE"` |
| `type` | enum | `ley`, `real_decreto`, `orden`, `resolucion`, etc. |
| `title_original` | string | Título oficial completo del BOE |
| `date_published` | ISO 8601 | Fecha de publicación oficial |
| `url_oficial` | string | Enlace permanente al BOE |
| **`summary_plain_es`** | string | **Resumen en lenguaje ciudadano (150-300 palabras)** |
| `keywords` | array[string] | 5-8 palabras clave |
| `topic_primary` | enum | `economía`, `empleo`, `sanidad`, `educación`, etc. |
| `approved_by` | string | Organismo que aprueba |
| `affects_to` | array[enum] | `["autónomos", "empresas", "todos_ciudadanos", ...]` |
| **`impact_index`** | object | `{score: 0-100, reason: "..."}` |
| `changes_summary` | string | Qué cambia respecto a antes (opcional) |
| `entry_into_force` | ISO 8601 | Fecha de entrada en vigor |
| **`transparency_notes`** | string | **Por qué los ciudadanos deben saberlo** |
| `version` | string | `"1.0"` |
| `created_at` | ISO 8601 | Timestamp de creación |
| `updated_at` | ISO 8601 | Timestamp de última actualización |

**Ver schema completo**: `data/schema/documento-publico-v1.schema.json`

---

## 🎨 Filosofía del Proyecto

> "Que una persona normal pueda entender qué se ha aprobado y cómo le afecta"

### Principios Editoriales

1. **Objetividad**: Presentamos hechos, no opiniones políticas
2. **Claridad**: Lenguaje comprensible sin sacrificar precisión
3. **Transparencia**: Siempre enlazamos a fuentes oficiales (BOE)
4. **Accesibilidad**: Diseño inclusivo, texto para todos
5. **No sensacionalismo**: Sin clickbait ni alarmismo
6. **Pedagogía cívica**: Explicamos el "por qué" y el "para qué"
7. **Apartidismo**: Vigilamos a todos por igual

### Guía de Estilo

**✅ Hacer**:
- "Esto te afecta si eres autónomo..."
- "Podrás deducir hasta 2.000€ en..."
- "Antes solo podías X, ahora también Y"

**❌ Evitar**:
- Tecnicismos sin explicar: "disposición derogatoria tercera"
- Lenguaje partidista: "El Gobierno dice que..."
- Sensacionalismo: "Escándalo de..."

---

## 🛠️ Troubleshooting

### Error: `OPENAI_API_KEY not found`

**Solución**: Configura tu API key en `.env`:
```bash
echo 'OPENAI_API_KEY=sk-tu-clave-aqui' >> .env
```

### Error: `Schema file not found`

**Solución**: Asegúrate de que existe `data/schema/documento-publico-v1.schema.json`. Si no existe, el schema se crea automáticamente al instalar el proyecto.

### BOE scraper no encuentra documentos

**Causas posibles**:
1. El BOE aún no ha publicado el sumario del día (se publica ~8:00 AM)
2. Cambio en la estructura HTML del BOE → reportar issue en GitHub

**Solución temporal**: Prueba con una fecha anterior:
```bash
./boe_scraper.py --date 2026-01-27
```

### LLM genera resúmenes con tecnicismos

**Solución**: Esto puede ocurrir ocasionalmente. Revisa manualmente los resúmenes con:
```bash
./validator.py data/jsonl/2026/01/boe-2026-01.jsonl --verbose
```

Los warnings te indicarán qué documentos tienen exceso de jerga técnica.

---

## 📈 Roadmap

### ✅ Fase 1: MVP BOE España (Actual)

- [x] Scraper de BOE (Sección I - Disposiciones generales)1
- [x] Procesador LLM para resúmenes ciudadanos
- [x] Validador de schema y calidad
- [x] Generador de índices JSON
- [ ] Automatización diaria (GitHub Actions)

### 🔄 Fase 2: Mejora Semántica (Q2 2026)

- [ ] Revisión humana de resúmenes (editorial mínimo)
- [ ] Mejor cálculo de `impact_index` basado en feedback
- [ ] Búsqueda textual semántica
- [ ] Sistema de alertas por email
- [ ] API pública REST

### 🚀 Fase 3: Integración Contratación Pública (Q3-Q4 2026)

- [ ] Scraper de PLACSP (licitaciones públicas)
- [ ] Matching semántico BOE ↔ licitaciones
- [ ] Indicador de transparencia en contratación
- [ ] Web completa Next.js con ambos datasets

---

## 🤝 Contribuir

Este es un proyecto cívico abierto. Contribuciones bienvenidas:

1. **Reporta bugs**: Abre un issue en GitHub
2. **Mejora prompts LLM**: Si encuentras resúmenes poco claros, propón mejoras
3. **Valida manualmente**: Comparte feedback sobre la calidad de los resúmenes
4. **Desarrolla**: Fork + PR con mejoras al código

**Código de conducta**: Mantemos un tono respetuoso, apartidista y pedagógico.

---

## 📄 Licencia

**Código**: MIT License  
**Datos (JSONL)**: CC BY 4.0 (Atribución)

El contenido original del BOE es público y del Estado Español. Este proyecto solo lo estructura y traduce para mejorar su accesibilidad.

---

## 📞 Contacto

- **Proyecto**: El Vigilante
- **GitHub**: [github.com/elvigilante](https://github.com/elvigilante)
- **Email**: contacto@elvigilante.org (placeholder)

---

**Nota**: Este es un proyecto MVP en desarrollo activo. La precisión de los resúmenes LLM mejorará con feedback y ajustes iterativos de prompts.

**El Vigilante**: Traductor ciudadano del BOE 🇪🇸
# Ley-Abierta
