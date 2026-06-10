# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-09
**Fase activa:** Diagnóstico — Análisis de scores inflados y limitaciones de Apify.

**Cambios de esta sesión:**

1. **Pipeline ejecutado correctamente:** 30 ofertas nuevas, 30 evaluadas, 0 errores, avg 0.431, Telegram enviado. ✅
2. **Diagnóstico de scores inflados:** Detectado que la oferta #1 (score 98) es `stretch` con solo 1 core skill genérica y `experience_min=0`. No es error de la fórmula, sino de los datos de entrada.
3. **Problema raíz identificado:** El actor de Apify (`alvaraaz/infojobs-actor`) NO extrae la sección estructurada "Requisitos" de InfoJobs (estudios, idiomas, conocimientos, experiencia mínima real). Solo captura la descripción libre.
4. **Skills mal extraídas:** gemma4 extrae solo 1-2 skills por oferta desde la descripción, cuando ofertas como FIGUERAS tienen 8+ requisitos reales. Con pocas skills, cualquier coincidencia da score perfecto.
5. **Licencia cambiada:** MIT → AGPL-3.0. LICENSE reemplazado, README badge actualizado. Commit `6c56698`.
6. **ADR-016 creado:** Documenta la decisión de reemplazar Apify con un scraper propio (requests + BeautifulSoup).
7. **PLANS.md actualizado:** Nueva Fase 7 con tareas T-A1 (scraper) y T-A2 (migración).
8. **MEMORIES.md actualizado:** Limitaciones de Apify documentadas.
9. **PIPELINE.md, adr/README.md** actualizados.

**Próximo paso — T-A1: Implementar scraper propio (infojobs_scraper.py):**

1. Crear `src/pipeline/infojobs_scraper.py` con:
   - `search_infojobs(keywords)` → GET a search results, parsea lista de ofertas
   - `scrape_offer_detail(offer_id, link)` → GET a oferta individual, extrae Requisitos estructurados (estudios, experiencia, idiomas, conocimientos, sector)
   - `parse_requisitos(soup)` → parser de la sección Requisitos del HTML
2. Reemplazar Apify en fetch.py (`actor_client.call()`) con el nuevo scraper
3. Flag `--use-apify` como fallback durante migración
4. Validar contra ofertas reales comparando campos
5. Requisitos adicionales: `beautifulsoup4` + `lxml` en requirements.txt
6. `.env.example`: APIFY_TOKEN pasa a ser opcional

**Pendiente (futuro):**
- T-5h Fase 2 (branding + microcopy)
- Fase 4 (role_discovery, market_signals, strategic_advisor)
- T-A2: Migración completa, eliminar Apify

**Bloqueados:** ninguno
**Tests:** 171 passing ✅
