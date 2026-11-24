# Diario de desarrollo

Registro de lo que hago en cada sesión, las decisiones que tomo y por qué,
y los problemas que encuentro.

---

## 2026-11-24 · Sesión 1: configuración del proyecto

### Qué he hecho
- Creo el repositorio `rag-normativa-uca` en GitHub y lo clono en `C:\Developer`.
- Creo un entorno virtual (`.venv`) para el proyecto.
- Instalo PyMuPDF y creo el `requirements.txt`.
- Configuro el `.gitignore` para no subir los documentos originales.
- Reúno un corpus inicial de 7 documentos y los registro en `data/sources.csv`.

### Decisiones
- **Licencia MIT**: es permisiva y la más habitual en proyectos personales. Cubre mi
  código, no los documentos de la UCA.
- **Un entorno virtual propio** para evitar conflictos
  de versiones y que `requirements.txt` refleje solo lo que usa este proyecto.
- **`requirements.txt` escrito a mano** con versiones fijadas (`pymupdf==2.1`), solo
  con las dependencias directas, en lugar de usar `pip freeze`.
- **PyMuPDF tiene licencia AGPL-3.0.** La mantengo porque el repositorio es público y
  abierto, así que cumplo con publicar el código. Alternativas permisivas si hiciera
  falta: `pypdf` (BSD) o `pdfplumber` (MIT).
- **Los PDFs no se suben al repositorio** (`data/raw/*` en el `.gitignore`), porque
  tienen sus propios derechos. Para que sea reproducible, `data/sources.csv` guarda la
  URL de cada uno. Mantengo la carpeta con `.gitkeep`.
- **Corpus inicial de 7 documentos** (unas 60 páginas): basta para construir y evaluar
  el pipeline. Ampliarlo más adelante puede ser un experimento por sí mismo.

### Problemas y soluciones
- **PowerShell no dejaba activar el entorno** ("la ejecución de scripts está
  deshabilitada"). Solución: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`,
  que permite scripts locales solo para mi usuario.
- **Excepción en el `.gitignore`**: `data/raw/` con `!data/raw/.gitkeep` no funciona,
  porque Git no mira dentro de una carpeta ignorada. Hay que usar `data/raw/*`.

---

## 2026-11-24 · Sesión 2: análisis exploratorio de los documentos

### Análisis manual

| Documento | Págs. | Estructura | Ruido | Tablas o listas | Relación con otros | Utilidad |
|---|---|---|---|---|---|---|
| reglamento_marco_tfg_uca_2012 | 9 | | | | Modificado por tfg_uca_2014 | |
| modificacion_reglamento_tfg_uca_2014 | 4 | | | | Modifica tfg_uca_2012 | |
| reglamento_tfgm_esi | 17 | | | | | |
| calendario_tfgm_esi_2026_27 | 1 | | | | | |
| rubrica_evaluacion_tfg_esi | 2 | | | | | |
| reglamento_practicas_externas_uca_2012 | 22 | | | | Modificado por practicas_uca_2015 | |
| modificacion_reglamento_practicas_uca_2015 | 7 | | | | Modifica practicas_uca_2012 | |

### Lo que ve el programa (extracción con PyMuPDF)
- Orden del texto:
- Encabezados y pies de página:
- Guiones y saltos de línea:
- Tablas:

### Conclusiones (requisitos para el script de extracción)
1.
2.
3.

### Dudas abiertas
-