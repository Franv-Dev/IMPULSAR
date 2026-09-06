# Auditoría visual general — IMPULSAR (29/8)

Fecha: 29/8/2026. Alcance: todo lo ya cerrado y pusheado hasta esa fecha (Home, Cuenta, Perfil público, Emprendedor: Solicitudes + Publicar) más una revisión rápida de consistencia contra los mockups de Design disponibles. Método: clon de solo lectura de dev_tomy (066842d) + lectura de `static/css/styles.css` y templates + render de los `.dc.html` de Design con Playwright para comparar contra mockup.

No se tocó código. Esto es un relevamiento para decidir qué tomar.

---

## 1. Hallazgos concretos (archivo + línea)

### 1.1 Resto textual de la paleta vieja en el fallback del mapa

Archivos: `app/blog/templates/blog/detail.html:453` y `app/perfil/templates/profile.html:512`

```js
new maplibregl.Marker({ color: "var(--color-primary, #6C63FF)" })
```

`#6C63FF` es el violeta original (el que precedió incluso al `#665DF1` ya descartado), de antes del rediseño índigo. El fallback nunca se dispara en la práctica (la variable CSS siempre existe), así que hoy no se ve mal — pero es texto muerto de la paleta vieja en dos pantallas ya "cerradas y pusheadas". Cambiar el fallback a `#3E2F94` (o directamente sacarlo, MapLibre acepta el string tal cual sin fallback). Costo: trivial, una línea por archivo.

### 1.2 Targets táctiles bajo el mínimo recomendado (44px, o 32px como piso)

Confirmado con el CSS real:

- `.share-btn` (`static/css/styles.css:4205`) — botón de compartir en cards y detalle. `font-size: 1rem; padding: 0.15rem 0.3rem;` sin `min-width`/`min-height` → área real ≈ 26×21px.
- `.eventos-lista__acciones .btn` (`static/css/styles.css:2252`) y `.btn--chico` (`static/css/styles.css:1300`) — Editar/Eliminar de eventos en Perfil, y botones chicos en Solicitudes (Emprendedor). `font-size: 0.8rem; padding: 0.3rem 0.8rem;` → alto real ≈ 27px.

Estos tres selectores cubren prácticamente todos los targets chicos del sitio. Arreglo de bajo costo y alto impacto: agregar `min-height: 32px; display: inline-flex; align-items: center;` (o 44px si se quiere ir al estándar completo de accesibilidad táctil) a los tres. No cambia el tamaño visual del texto/ícono, solo el área clicable.

Prioridad: alta, esfuerzo: bajo.

### 1.3 Pantalla "Explorar" — mockup con filtros sin respaldo de datos (en ese momento)

El mockup (`IMPULSAR Rediseño.dc.html`, artboard "Explorar") mostraba:

- Filtro de Distancia con radio configurable (no solo "Cerca de mí" como botón simple, que era lo único que existía entonces).
- Checkboxes "Solo verificados", "Con reseñas", "Abierto ahora".

Nota de diseño importante: "Solo verificados" es el mismo dato falso que ya se sacó de otras pantallas — no hay verificación real a nivel Post, solo a nivel Service. Si se encara "Explorar" como pantalla, ese checkbox tiene que omitirse o reformularse, no puede volver a aparecer tal como está en el mockup.

Actualización: esta pantalla ya se encaró y se cerró (radio + reseñas + "Abierto ahora" activados; "Solo verificados" descartado por dato falso) — ver `docs/CONTEXTO.md` para el estado final.

---

## 2. Lo que estaba bien (para que quede documentado, no solo lo que falla)

- Sistema de tokens de color: consistente, bien comentado, con justificación WCAG explícita línea por línea. Modo oscuro completo y paralelo, no un afterthought. Nivel de rigor que vale la pena mantener como estándar para todo lo nuevo.
- Sistema de componentes reusado de verdad: `.card`/`.card__*`, `.btn--primary/secondary/ghost`, `.review-card` se repiten idénticos en blog, servicios, turnos, productos y perfil — no hay fragmentación de markup por pantalla.
- Perfil público, Home, Emprendedor: implementación fiel al mockup en estructura y jerarquía. El patrón de permiso 100% server-side en el panel del dueño (no solo ocultar con CSS) es correcto.
- Honestidad de datos aplicada consistentemente: el criterio de "sin dato real, se omite" se nota en el código, no solo en la documentación — hay comentarios en CSS y templates explicando por qué algo se omitió.

---

## 3. Comparativo mockup vs. lo implementado (pantallas cerradas a esa fecha)

"Perfil del emprendedor" (mockup) contra `app/perfil/templates/profile.html` (real): estructura 1:1 — hero, "Tus números" (panel del dueño), Mis emprendimientos, Próximos eventos, Horarios, Ubicación. Sin desvíos que no estén ya documentados (botón "Enviar mensaje" disabled, sin badge Verificado, etc.).

"Inicio" (mockup) vs. Home real: el banner de publicidad completo estaba correctamente omitido (backlog de monetización). El resto del mockup (buscador de 3 campos, rubros con conteo, destacados, cartelera) coincidía con lo cerrado a esa fecha. Nota: el Home tuvo una segunda pasada de rediseño el 6/9 (buscador unificado, rubros con ícono, cards verticales) — ver `docs/CONTEXTO.md`.

---

## Actualización 29/8 — hallazgo nuevo durante verificación posterior

**Desborde horizontal en mobile: `.orden` en `/blog/`**

Confirmado con el CSS real (`static/css/styles.css:1086-1103`, `app/blog/templates/blog/index.html:168-177`). Causa: `.orden` es `display:flex` sin `flex-wrap` y sin ningún media query — label "Ordenar por" + 3 botones de texto todos en una sola fila, sin el breakpoint estándar de 480px que usa el resto de la hoja.

Es un control 100% decorativo (disabled a propósito, UI-first), así que no hacía falta rediseño: alcanzaba con contenerlo (`flex-direction: column` bajo 480px, o `flex-wrap: wrap` en `.orden__grupo`). Ya resuelto como CSS puro, sin tests nuevos necesarios.
