# El Vigilante - ETL Workflow (2025 Master Database)

Este documento contiene todos los comandos necesarios para crear la **Base de Datos Maestra** de leyes estatales de España del año 2025.

---

## 📋 FLUJO COMPLETO (3 PASOS)

### **PASO 1: EXTRACT** - Cosecha Masiva de Datos BOE (2025)

Este paso descarga todos los documentos del BOE del año 2025 y genera archivos JSONL mensuales.

```bash
# Ejecutar el harvester para todo el año 2025
# ADVERTENCIA: Este proceso puede tardar varias horas
python3 harvest_year.py --year 2025
```

**Variantes útiles:**

```bash
# Modo dry-run (previsualización sin ejecutar)
python3 harvest_year.py --year 2025 --dry-run

# Reanudar desde una fecha específica (útil si se interrumpe)
python3 harvest_year.py --year 2025 --resume-from 2025-06-15
```

**Salida esperada:**
- Archivos JSONL en: `data/jsonl/2025/01/`, `data/jsonl/2025/02/`, ..., `data/jsonl/2025/12/`
- PDFs en: `data/pdfs/2025/01/`, `data/pdfs/2025/02/`, etc.
- Logs en: `logs/boe_scraper.log` y `logs/harvest_errors_2025.log`

---

### **PASO 2: TRANSFORM** - Procesamiento con IA (LLM)

Este paso enriquece los documentos con resúmenes, traducciones y análisis generados por LLM.

```bash
# Procesar todos los archivos JSONL del año 2025 con LLM
python3 process_with_llm.py --input-dir data/jsonl/2025/ --recursive
```

**Variantes útiles:**

```bash
# Procesar solo un mes específico
python3 process_with_llm.py --input-dir data/jsonl/2025/01/

# Procesar con límite de documentos (testing)
python3 process_with_llm.py --input-dir data/jsonl/2025/ --recursive --limit 50

# Modo dry-run (verificar sin procesar)
python3 process_with_llm.py --input-dir data/jsonl/2025/ --recursive --dry-run
```

**Salida esperada:**
- Archivos JSONL enriquecidos en: `data/jsonl/2025/01/boe-2025-01_enriched.jsonl`, etc.
- Los archivos originales permanecen intactos (se crean archivos nuevos con sufijo `_enriched`)

---

### **PASO 3: LOAD** - Fusión en Archivo Maestro

Este paso fusiona todos los archivos JSONL mensuales en un único archivo `master_2025.jsonl`.

```bash
# Fusionar todos los archivos enriquecidos en un solo archivo maestro
find data/jsonl/2025/ -name "*_enriched.jsonl" -type f | sort | xargs cat > data/master_2025.jsonl
```

**Verificación:**

```bash
# Contar total de documentos en el archivo maestro
wc -l data/master_2025.jsonl

# Ver estadísticas del archivo
du -h data/master_2025.jsonl

# Ver primeros 3 documentos (formateados)
head -n 3 data/master_2025.jsonl | jq .

# Verificar integridad JSON (cada línea debe ser JSON válido)
cat data/master_2025.jsonl | jq -c . > /dev/null && echo "✓ JSON válido" || echo "✗ JSON inválido"
```

---

## 🚀 EJECUCIÓN COMPLETA (UN SOLO COMANDO)

Si deseas ejecutar los 3 pasos de forma secuencial:

```bash
#!/bin/bash
# etl_full_pipeline.sh

echo "=== PASO 1: EXTRACT ==="
python3 harvest_year.py --year 2025

echo ""
echo "=== PASO 2: TRANSFORM ==="
python3 process_with_llm.py --input-dir data/jsonl/2025/ --recursive

echo ""
echo "=== PASO 3: LOAD ==="
find data/jsonl/2025/ -name "*_enriched.jsonl" -type f | sort | xargs cat > data/master_2025.jsonl

echo ""
echo "=== VERIFICACIÓN ==="
wc -l data/master_2025.jsonl
du -h data/master_2025.jsonl

echo ""
echo "✓ ETL Pipeline completado"
```

**Ejecutar el pipeline completo:**

```bash
chmod +x etl_full_pipeline.sh
./etl_full_pipeline.sh
```

---

## 🔧 COMANDOS ÚTILES DE MANTENIMIENTO

### Limpiar datos parciales (reiniciar desde cero)

```bash
# ⚠️  CUIDADO: Esto eliminará todos los datos descargados
rm -rf data/jsonl/2025/
rm -rf data/pdfs/2025/
rm -f logs/harvest_errors_2025.log
```

### Estadísticas por mes

```bash
# Contar documentos por mes
for month in {01..12}; do
  count=$(find data/jsonl/2025/$month/ -name "*.jsonl" -exec wc -l {} + 2>/dev/null | tail -n 1 | awk '{print $1}')
  echo "2025-$month: $count documentos"
done
```

### Verificar progreso durante la cosecha

```bash
# Monitorear logs en tiempo real
tail -f logs/boe_scraper.log
```

### Buscar documentos específicos en el archivo maestro

```bash
# Buscar leyes que contengan "vivienda"
cat data/master_2025.jsonl | jq 'select(.title_original | contains("vivienda"))'

# Contar documentos por tipo
cat data/master_2025.jsonl | jq -r '.type' | sort | uniq -c | sort -rn
```

---

## 📊 ESTIMACIONES DE TIEMPO Y RECURSOS

- **PASO 1 (EXTRACT)**: 
  - Duración: ~6-12 horas (365 días × ~1-2 min/día)
  - Almacenamiento: ~5-20 GB (PDFs + JSONL)

- **PASO 2 (TRANSFORM)**:
  - Duración: Variable (depende del proveedor de LLM y número de documentos)
  - Costo: Consultar límites de API del proveedor LLM

- **PASO 3 (LOAD)**:
  - Duración: <1 minuto
  - Almacenamiento: ~100-500 MB (archivo maestro comprimido)

---

## 🎯 RESULTADO FINAL

Al completar el flujo ETL, obtendrás:

✅ **`data/master_2025.jsonl`** - Base de datos maestra con todas las leyes de 2025
✅ Cada línea = 1 documento con:
  - Metadata completa (título, fecha, tipo, URL, etc.)
  - Texto completo extraído del PDF
  - Resumen generado por IA
  - Clasificación temática
  - Índice de impacto
  - Palabras clave
  - Grupos afectados

Este archivo está listo para ser consumido por una web estática, API o cualquier otro sistema de visualización.
