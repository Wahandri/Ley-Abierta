# 🌐 Contexto para Desarrollo Web: El Vigilante 2025

Este documento sirve como **contexto maestro** para el asistente IA que desarrollará la web.

## 🎯 Objetivo del Proyecto
Crear una **web estática moderna y rápida** para visualizar todas las leyes estatales de España aprobadas en 2025.
La web debe ser "ciudadana-first": simple, bonita, sin jerga legal y directa al grano.

## 📦 Assets Disponibles
Todo el contenido está en un único archivo JSONL maestro que debes consumir.

- **Archivo de datos:** `public/data/master_2025.jsonl`
- **Total documentos:** ~845 leyes.
- **Formato:** JSON Lines (cada línea es un objeto JSON válido).

### Estructura de cada Documento (JSON)
```json
{
  "id": "boe-2025-01-02-resolucion-8e4bff4d",
  "short_title": "Lista de admitidos para oposiciones de Hacienda",  // <--- USAR ESTE COMO TÍTULO PRINCIPAL
  "title_original": "Resolución de 26 de diciembre...",
  "type": "resolucion",  // ley, real_decreto, orden, etc.
  "date_published": "2025-01-02T00:00:00",
  "url_oficial": "https://www.boe.es/...",
  "pdf_path": "pdfs/2025/01/...",
  "summary_plain_es": "Resumen en lenguaje sencillo generado por IA...",
  "keywords": ["oposiciones", "hacienda", "empleo público"],
  "affects_to": ["opositores", "funcionarios"],
  "transparency_notes": "Nota sobre por qué esto es relevante...",
  "impact_index": {"score": 35, "reason": "..."}
}
```

## 🛠️ Requisitos Técnicos Sugeridos
- **Framework:** Next.js (App Router) + Static Export (`output: 'export'`).
- **Estilos:** Tailwind CSS (Diseño limpio, tipografía excelente, modo oscuro elegante).
- **Búsqueda:** Buscador instantáneo (cliente) usando `fuse.js` o similar (el JSONL es ligero, ~2MB).
- **Filtros:** Por mes, por tipo de ley, por audiencia ("afecta a pensionistas").

## 🎨 Guía de Diseño (Aesthetics)
- **Estilo:** "Periódico Digital Minimalista".
- **Color:** Blanco/Negro con acentos sutiles (ej: Rojo pálido para prohibiciones, Verde para ayudas).
- **Tipografía:** Serif moderna para títulos (ej: Merriweather), Sans para textos.
- **UX:**
  - Tarjetas grandes con el `short_title` destacado.
  - El título oficial (`title_original`) debe ir en pequeño/secundario.
  - Badges para `type` (Ley, Real Decreto...).

## 🚀 Instrucciones para el Asistente Web
1. **NO** intentes scrapear nada. Los datos YA están en `master_2025.jsonl`.
2. **Copia** este archivo a `public/data/`.
3. Crea un script de build o usa `getStaticProps/generateStaticParams` para leer el JSONL y generar las páginas estáticas.
4. Prioriza el campo `short_title` sobre `title_original`.
