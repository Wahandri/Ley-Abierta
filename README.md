# El Vigilante - BOE Scraper

**Sistema automatizado para traducir documentos oficiales del BOE a lenguaje claro y accesible**

---

## 📖 Descripción

El Vigilante es una herramienta que procesa automáticamente los documentos publicados en el Boletín Oficial del Estado (BOE) y los transforma en contenido comprensible para cualquier ciudadano.

### El Problema

Los documentos oficiales del BOE utilizan lenguaje técnico-jurídico que dificulta su comprensión para la mayoría de la población. Esto genera:

- **Desinformación**: La ciudadanía no entiende qué se aprueba ni cómo le afecta
- **Falta de acceso**: El lenguaje burocrático actúa como barrera de entrada
- **Desincentivo cívico**: La complejidad desalienta el seguimiento de asuntos públicos

### La Solución

Este proyecto automatiza tres procesos clave:

1. **Descarga**: Obtiene documentos oficiales del BOE diariamente
2. **Extracción**: Procesa los PDFs y extrae su contenido en texto plano
3. **Traducción**: Utiliza IA para generar resúmenes en lenguaje ciudadano

**Resultado**: JSON estructurado listo para mostrar en una web, app móvil o cualquier interfaz.

---

## 🎯 Para Quién Es Este Proyecto

### Usuarios Finales
- Ciudadanos que quieren entender las leyes sin ser abogados
- Autónomos y empresarios que necesitan conocer cambios normativos
- Estudiantes e investigadores de políticas públicas

### Desarrolladores
- Implementadores de portales de transparencia
- Creadores de apps cívicas
- Periodistas de datos

### Organizaciones
- ONGs de transparencia y participación ciudadana
- Administraciones públicas que quieren mejorar la comunicación
- Medios de comunicación

---

## ✨ Características Principales

### 🤖 Procesamiento Automatizado
- Descarga automática de documentos del BOE
- Extracción de texto desde PDFs (hasta 20 páginas por documento)
- Procesamiento con IA (OpenAI) para generar contenido comprensible

### 📝 Contenido Generado
Cada documento se enriquece con:
- **Resumen en español sencillo** (150-300 palabras)
- **Palabras clave** para facilitar búsquedas
- **Grupos afectados** (autónomos, empresas, estudiantes, etc.)
- **Clasificación por tema** (economía, sanidad, educación, etc.)
- **Notas de transparencia**: Por qué es importante conocer este documento

### 🔒 Calidad y Trazabilidad
- Validación automática de datos generados
- Enlace siempre a la fuente oficial del BOE
- Versionado de datos para auditoría
- Caché de respuestas para evitar reprocesamiento

---

## 🚀 Instalación Rápida

### Requisitos Previos
- Python 3.11 o superior
- Cuenta de OpenAI con API key ([obtener aquí](https://platform.openai.com/api-keys))
- 4GB de espacio en disco (para PDFs y datos)

### Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/el-vigilante-scraper.git
cd el-vigilante-scraper

# 2. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar API key
cp .env.example .env
# Editar .env y añadir: OPENAI_API_KEY=tu-clave-aqui
```

---

## 📚 Uso

### Flujo Completo (Recomendado)

```bash
# 1. Scraper: Descarga PDFs y extrae texto (sin usar IA)
python3 boe_scraper.py --date 2026-01-27 --limit 5

# 2. Procesar con IA: Genera resúmenes y análisis
python3 process_with_llm.py data/jsonl/2026/01/boe-2026-01.jsonl

# 3. Validar calidad de datos
python3 validator.py data/jsonl/2026/01/boe-2026-01.jsonl

# 4. Generar índices para web (opcional)
python3 index_generator.py --generate-latest
```

### Comandos Individuales

**Scraper básico:**
```bash
# Procesar BOE de hoy
python3 boe_scraper.py --date today --limit 10

# Fecha específica
python3 boe_scraper.py --date 2026-01-27
```

**Procesamiento con IA:**
```bash
# Procesar archivo JSONL
python3 process_with_llm.py data/jsonl/2026/01/boe-2026-01.jsonl
```

**Validación:**
```bash
# Validar datos generados
python3 validator.py data/jsonl/2026/01/boe-2026-01.jsonl
```

---

## 📂 Estructura de Datos

### Archivos Generados

```
data/
├── pdfs/                    # PDFs descargados del BOE
│   └── 2026/01/
│       └── boe-2026-01-27-*.pdf
├── jsonl/                   # Datos procesados
│   └── 2026/01/
│       └── boe-2026-01.jsonl
├── index/                   # Índices para consumir en web
│   ├── latest.json         # Últimos 30 días
│   └── topics.json         # Agrupados por tema
└── cache/
    └── llm_responses/      # Caché de IA
```

### Formato de Datos (JSON)

Cada documento se estructura con estos campos principales:

```json
{
  "id": "boe-2026-01-27-acuerdo-56de5cbe",
  "title_original": "Acuerdo internacional...",
  "date_published": "2026-01-27",
  "url_oficial": "https://www.boe.es/...",
  "pdf_path": "pdfs/2026/01/boe-2026-01-27-acuerdo-56de5cbe.pdf",
  
  "summary_plain_es": "Resumen en lenguaje sencillo del documento...",
  "keywords": ["cooperación", "desarrollo", "OCDE"],
  "topic_primary": "economía",
  "affects_to": ["todos_ciudadanos", "empresas"],
  "transparency_notes": "Es importante porque..."
}
```

**Ver schema completo:** [`data/schema/documento-publico-v1.schema.json`](data/schema/documento-publico-v1.schema.json)

---

## ⚙️ Configuración

### Variables de Entorno (`.env`)

```env
# OpenAI API Key (OBLIGATORIO)
OPENAI_API_KEY=sk-tu-clave-aqui

# Modelo de IA a usar
LLM_MODEL=gpt-4o-mini

# Tokens máximos por respuesta
LLM_MAX_TOKENS=1000

# Temperatura (creatividad: 0.0 = preciso, 1.0 = creativo)
LLM_TEMPERATURE=0.3
```

### Costes Estimados

Con **gpt-4o-mini**:
- ~$0.002-0.005 por documento
- Procesando 10 docs/día: ~$1-2/mes
- Procesando 100 docs/día: ~$10-15/mes

---

## 🛠️ Solución de Problemas

### Error: `OPENAI_API_KEY not found`
**Solución:** Configurar la API key en el archivo `.env`:
```bash
echo 'OPENAI_API_KEY=sk-tu-clave-aqui' >> .env
```

### Error: `No module named 'pdfplumber'`
**Solución:** Instalar dependencias:
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### El scraper no encuentra documentos
**Causas posibles:**
1. El BOE aún no publicó el sumario (se publica ~8:00 AM)
2. Fecha futura (el BOE solo publica documentos pasados)
3. Cambio en estructura HTML del BOE

**Solución:** Usar una fecha pasada reciente:
```bash
python3 boe_scraper.py --date 2026-01-20
```

---

## 🎨 Principios del Proyecto

### Neutralidad
Este proyecto NO toma posiciones políticas. Su único objetivo es hacer accesible información pública ya existente.

### Transparencia
- Todo el código es open source
- Los datos siempre enlazan a fuentes oficiales
- El procesamiento es auditable y reproducible

### Accesibilidad
- Lenguaje claro sin tecnicismos innecesarios
- Explicaciones pedagógicas, no simplificaciones
- Datos estructurados consumibles por cualquier plataforma

### No Sensacionalismo
- Presentación objetiva de hechos
- Sin clickbait ni titulares alarmistas
- Enfoque educativo, no escandaloso

---

## 🤝 Contribuir

Las contribuciones son bienvenidas. Puedes ayudar:

1. **Reportando errores:** Abre un [issue en GitHub](https://github.com/tu-usuario/el-vigilante-scraper/issues)
2. **Mejorando código:** Fork + Pull Request
3. **Validando resúmenes:** Reporta resúmenes poco claros para mejorar prompts
4. **Documentando:** Mejora esta documentación

**Código de conducta:** Mantener tono respetuoso, neutral y constructivo.

---

## 📄 Licencia

- **Código:** MIT License
- **Datos (JSONL):** CC BY 4.0 (Creative Commons - Atribución)

Los documentos originales del BOE son de dominio público del Estado Español.

---

## 📞 Contacto y Enlaces

- **Repositorio:** [github.com/tu-usuario/el-vigilante-scraper](https://github.com/tu-usuario/el-vigilante-scraper)
- **Documentación:** Este README
- **Issues:** [GitHub Issues](https://github.com/tu-usuario/el-vigilante-scraper/issues)

---

## 🗺️ Roadmap

### ✅ Versión Actual (v1.0)
- [x] Scraper de BOE con descarga de PDFs
- [x] Extracción de texto con pdfplumber
- [x] Procesamiento con IA (resúmenes automáticos)
- [x] Validación de calidad de datos
- [x] Generación de índices JSON

### 🔄 Próximas Versiones
- [ ] Automatización con GitHub Actions (ejecución diaria)
- [ ] API REST para consultar datos
- [ ] Mejoras en clasificación de temas
- [ ] Soporte para BOEs autonómicos (DOGC, BOJA, etc.)
- [ ] Sistema de alertas personalizadas

---

**El Vigilante**: Traduciendo burocracia, democratizando información 🇪🇸
