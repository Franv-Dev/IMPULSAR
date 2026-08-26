let ALL_POSTS = [];

// Utilidad básica para evitar inyección de HTML
function escapeHtml(str) {
    return String(str || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// El corazon de favorito de una tarjeta de la home.
//
// Es el mismo <form> POST con CSRF que arma partials/_favorito_boton.html en el
// servidor, y no un fetch: asi el toggle sigue siendo una sola ruta
// (blog.toggle_favorite), que ya redirige de vuelta a donde estabas. El token
// sale del <meta name="csrf-token"> de base.html, que es el de la sesion.
function botonFavorito(post, title) {
    const token = document.querySelector('meta[name="csrf-token"]');
    if (!token) return "";

    const activo = post.favorito;
    const etiqueta = activo ? "Quitar de favoritos" : "Agregar a favoritos";

    return `
        <form method="post" action="/blog/${post.id}/favorito" class="favorite-form">
            <input type="hidden" name="csrf_token" value="${escapeHtml(token.content)}">
            <button type="submit" class="favorite-btn ${activo ? "favorite-btn--active" : ""}"
                aria-pressed="${activo ? "true" : "false"}"
                aria-label="${etiqueta} ${title}"
                title="${etiqueta}">${activo ? "♥" : "♡"}</button>
        </form>
    `;
}

function renderPosts(posts) {
    const grid = document.getElementById("posts-grid");
    const emptyEl = document.getElementById("posts-empty");

    if (!grid) return;

    grid.innerHTML = "";

    if (!posts || posts.length === 0) {
        emptyEl.style.display = "block";
        return;
    } else {
        emptyEl.style.display = "none";
    }

    posts.forEach((post) => {
        const card = document.createElement("article");
        card.className = "card";

        const title = escapeHtml(post.title || "Emprendimiento sin título");
        const body = escapeHtml(post.body || "");
        // 160, el mismo recorte que usa la ficha del listado.
        const shortBody = body.length > 160 ? body.slice(0, 160) + "..." : body;

        // La tarjeta es la misma .ficha que arma el listado en el servidor
        // (ver app/blog/templates/blog/index.html): la home y /blog/ tienen que
        // verse iguales, y antes esta seguia siendo la tarjeta vieja.
        //
        // Solo se pinta lo que la API devuelve de verdad. El rediseño muestra
        // ademas el promedio de reseñas, la zona, los km y un sello
        // "Verificado": el promedio existe en la base pero /api/posts/ todavia
        // no lo manda, y los otros tres no existen (no hay barrio, no hay
        // distancia sin geolocalizar, y la verificacion es de cada servicio y
        // no del emprendimiento). Nada de eso se dibuja.
        const postDetailUrl = `/blog/${post.id}`;
        const postAbsoluteUrl = `${location.origin}${postDetailUrl}`;
        const postImageUrl = post.image ? `/static/uploads/${escapeHtml(post.image)}` : null;
        const categoryText = escapeHtml(post.category_label || "Sin categoría");

        card.className = "ficha ficha--vertical";

        const imagenHtml = postImageUrl
            ? `<img src="${postImageUrl}" alt="" class="ficha__img">`
            : "";

        // El corazon solo existe si la API mando "favorito", o sea si hay
        // sesion. Sin login no se dibuja un boton que iba a rebotar al login.
        const favoritoHtml =
            typeof post.favorito === "boolean" ? botonFavorito(post, title) : "";

        card.innerHTML = `
            <a href="${postDetailUrl}" class="ficha__foto" tabindex="-1" aria-hidden="true">
                ${imagenHtml}
            </a>
            <div class="ficha__cuerpo">
                <div class="ficha__tags">
                    <span class="badge badge--category">${categoryText}</span>
                    <div class="ficha__acciones">
                        <button type="button" class="share-btn"
                            data-share-url="${postAbsoluteUrl}"
                            data-share-title="${title}"
                            aria-label="Compartir ${title}"
                            title="Compartir">🔗</button>
                        ${favoritoHtml}
                    </div>
                </div>
                <h3 class="ficha__titulo">
                    <a href="${postDetailUrl}">${title}</a>
                </h3>
                <p class="ficha__desc">${shortBody}</p>
            </div>
        `;

        grid.appendChild(card);
    });
}
// Pide los emprendimientos al servidor. La busqueda se resuelve en la base de
// datos y no en el navegador: antes se descargaban TODOS los posts y se
// filtraban aca, lo que deja de funcionar apenas la plataforma crezca.
function fetchPosts(query, categoria) {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    // La API ignora una categoria que no existe, asi que no hace falta
    // validarla aca: alcanza con no mandar el parametro vacio.
    if (categoria) params.set("category", categoria);
    params.set("per_page", "12");

    return fetch(`/api/posts/?${params.toString()}`).then((res) => {
        if (!res.ok) throw new Error("Error al obtener los posts");
        return res.json();
    });
}

// Evita disparar una consulta por cada tecla que se aprieta.
function debounce(fn, ms) {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => fn(...args), ms);
    };
}

document.addEventListener("DOMContentLoaded", () => {
    const grid = document.getElementById("posts-grid");
    const errorEl = document.getElementById("posts-error");
    const loadingEl = document.getElementById("posts-loading");
    const searchForm = document.getElementById("search-form");
    const input = document.getElementById("search-text");
    const selectCategoria = document.getElementById("search-category");
    const cerca = document.getElementById("search-near");
    const lat = document.getElementById("search-lat");
    const lon = document.getElementById("search-lon");
    const botonCerca = document.getElementById("use-my-location-home");

    if (!grid) return; // no estamos en la home

    function cargar(query, categoria) {
        // En conexiones lentas la grilla queda vacia varios segundos sin este
        // aviso, y parece que la pagina no respondio.
        if (errorEl) errorEl.style.display = "none";
        if (loadingEl) loadingEl.style.display = "block";
        grid.innerHTML = "";

        fetchPosts(query, categoria)
            .then((data) => {
                ALL_POSTS = Array.isArray(data.items) ? data.items : [];
                renderPosts(ALL_POSTS);
            })
            .catch((err) => {
                console.error(err);
                if (errorEl) errorEl.style.display = "block";
            })
            .finally(() => {
                if (loadingEl) loadingEl.style.display = "none";
            });
    }

    // Los dos campos del buscador se leen juntos: filtrar por rubro no tiene
    // que perder lo que el usuario ya habia escrito, ni al reves.
    function cargarDesdeElFormulario() {
        cargar(
            input ? input.value.trim() : "",
            selectCategoria ? selectCategoria.value : ""
        );
    }

    // Si hay ubicacion, la busqueda se va al listado: es la unica pantalla que
    // ordena por distancia (consultas.buscar_posts la calcula en SQL). La home
    // filtra en vivo, pero no sabe de kilometros.
    function hayUbicacion() {
        return Boolean((cerca && cerca.value.trim()) || (lat && lat.value));
    }

    function irAlListadoConUbicacion() {
        const params = new URLSearchParams();
        const texto = input ? input.value.trim() : "";
        const categoria = selectCategoria ? selectCategoria.value : "";

        // Lo que el usuario ya habia cargado viaja con el; /blog/ lee los
        // mismos tres nombres (ver formulario.leer_busqueda, leer_cercania y
        // leer_categoria_de_filtro).
        if (texto) params.set("q", texto);
        if (categoria) params.set("category", categoria);

        if (lat && lat.value && lon && lon.value) {
            // Coordenadas del navegador: no hace falta geocodificar nada.
            params.set("lat", lat.value);
            params.set("lon", lon.value);
        } else if (cerca) {
            params.set("near", cerca.value.trim());
        }

        window.location.href = `/blog/?${params.toString()}`;
    }

    cargar("", "");

    // Si retoca la direccion a mano, las coordenadas de "Cerca de mí" quedan
    // viejas: sin esto el servidor usaria esas en vez del texto nuevo. Es el
    // mismo cuidado que ya tiene el buscador del listado.
    if (cerca) {
        cerca.addEventListener("input", () => {
            if (lat) lat.value = "";
            if (lon) lon.value = "";
        });
    }

    if (botonCerca) {
        botonCerca.addEventListener("click", () => {
            if (!navigator.geolocation) {
                alert("Tu navegador no soporta geolocalización.");
                return;
            }

            const textoOriginal = botonCerca.textContent;
            botonCerca.disabled = true;
            botonCerca.textContent = "Ubicando...";

            navigator.geolocation.getCurrentPosition(
                (posicion) => {
                    if (lat) lat.value = posicion.coords.latitude;
                    if (lon) lon.value = posicion.coords.longitude;
                    irAlListadoConUbicacion();
                },
                () => {
                    alert("No pudimos acceder a tu ubicación.");
                    botonCerca.disabled = false;
                    botonCerca.textContent = textoOriginal;
                }
            );
        });
    }

    if (searchForm) {
        searchForm.addEventListener("submit", (e) => {
            e.preventDefault();
            if (hayUbicacion()) {
                irAlListadoConUbicacion();
                return;
            }
            cargarDesdeElFormulario();
        });

        if (input) {
            input.addEventListener(
                "input",
                debounce(cargarDesdeElFormulario, 300)
            );
        }

        // El select no pasa por el debounce: elegir un rubro es un solo gesto
        // deliberado, no una tecla atras de otra.
        if (selectCategoria) {
            selectCategoria.addEventListener("change", cargarDesdeElFormulario);
        }
    }
});
// =============================
// SWITCH DE TEMA (CLARO / OSCURO)
// =============================
// El tema inicial ya lo resolvio el script inline del <head> de base.html
// (tiene que correr antes del primer pintado para que no parpadee). Aca solo
// esta el switch: cambiar el atributo, persistir la eleccion y mantener el
// estado accesible del boton.
const TEMA_STORAGE_KEY = "impulsar-tema";

function temaGuardado() {
    try {
        const valor = localStorage.getItem(TEMA_STORAGE_KEY);
        return valor === "dark" || valor === "light" ? valor : null;
    } catch (e) {
        return null; // modo privado / cookies bloqueadas
    }
}

function aplicarTema(tema, boton) {
    document.documentElement.setAttribute("data-theme", tema);
    if (boton) boton.setAttribute("aria-pressed", tema === "dark" ? "true" : "false");
}

document.addEventListener("DOMContentLoaded", () => {
    const boton = document.getElementById("theme-toggle");
    if (!boton) return;

    const temaActual = document.documentElement.getAttribute("data-theme") || "light";
    boton.setAttribute("aria-pressed", temaActual === "dark" ? "true" : "false");

    boton.addEventListener("click", () => {
        const nuevo =
            document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        aplicarTema(nuevo, boton);
        try {
            // A partir del primer click la eleccion manual pisa al sistema
            // operativo, incluso si despues el SO cambia de tema.
            localStorage.setItem(TEMA_STORAGE_KEY, nuevo);
        } catch (e) {
            // Sin persistencia el tema igual cambia, pero solo en esta pagina.
        }
    });

    // Mientras el usuario nunca haya tocado el switch, seguimos al sistema en
    // vivo: si cambia el tema del SO con la pestaña abierta, la pagina acompaña.
    const consultaSO = window.matchMedia("(prefers-color-scheme: dark)");
    consultaSO.addEventListener("change", (evento) => {
        if (temaGuardado()) return; // hay eleccion explicita: no la pisamos
        aplicarTema(evento.matches ? "dark" : "light", boton);
    });
});

// =============================
// MENÚ DE USUARIO EN LA NAVBAR
// =============================
document.addEventListener("DOMContentLoaded", () => {
    
    // --- LÓGICA MENÚ DE USUARIO (la que ya tenías) ---
    const userToggle = document.querySelector(".navbar__user-toggle");
    const userMenu = document.getElementById("user-menu");

    if (userToggle && userMenu) {
        // Abrir/cerrar menú al hacer click en el usuario
        userToggle.addEventListener("click", (event) => {
            event.stopPropagation();
            const abierto = userMenu.classList.toggle("user-menu--open");
            userToggle.setAttribute("aria-expanded", abierto ? "true" : "false");
        });

        // Cerrar menú al hacer click fuera
        document.addEventListener("click", () => {
            userMenu.classList.remove("user-menu--open");
            userToggle.setAttribute("aria-expanded", "false");
        });
    }

    // --- LÓGICA MENÚ MÓVIL (NUEVO) ---
    const mobileToggle = document.querySelector(".navbar__toggle");
    const navbar = document.querySelector(".navbar"); // El contenedor principal

    if (mobileToggle && navbar) {
        mobileToggle.addEventListener("click", (event) => {
            event.stopPropagation();
            // Añade/quita la clase .navbar--mobile-open al <header class="navbar">
            const abierto = navbar.classList.toggle("navbar--mobile-open");
            mobileToggle.setAttribute("aria-expanded", abierto ? "true" : "false");
        });
    }

    // Opcional: Cerrar menú móvil si se hace clic fuera de él (en 'main' o 'footer')
    const mainContent = document.querySelector("main");
    if (mainContent && navbar) {
        mainContent.addEventListener("click", () => {
            navbar.classList.remove("navbar--mobile-open");
            if (mobileToggle) mobileToggle.setAttribute("aria-expanded", "false");
        });
    }

});

// =============================
// BADGE DE NOTIFICACIONES (mensajes sin leer + reseñas sin responder)
// =============================
document.addEventListener("DOMContentLoaded", () => {
    const badge = document.getElementById("notif-badge");
    if (!badge) return; // no esta logueado, no existe el link de Mensajes

    function actualizarBadge() {
        fetch("/mensajes/notificaciones")
            .then((res) => (res.ok ? res.json() : Promise.reject(res)))
            .then((data) => {
                const total = data.total || 0;
                if (total > 0) {
                    badge.textContent = total > 9 ? "9+" : String(total);
                    badge.style.display = "inline-block";
                } else {
                    badge.style.display = "none";
                }
            })
            .catch(() => {
                // Un polling fallido no debe romper la navegacion normal.
            });
    }

    actualizarBadge();
    setInterval(actualizarBadge, 20000);
});

// =============================
// BÚSQUEDA POR CERCANÍA (listado de emprendimientos)
// =============================
document.addEventListener("DOMContentLoaded", () => {
    const boton = document.getElementById("use-my-location");
    const nearInput = document.getElementById("near-input");
    const latInput = document.getElementById("near-lat");
    const lonInput = document.getElementById("near-lon");

    if (!boton || !nearInput || !latInput || !lonInput) return; // no estamos en /blog/

    // Si el usuario retoca el texto a mano, las coordenadas anteriores (de
    // "Mi ubicación" o de una busqueda previa) quedan obsoletas: sin esto, el
    // servidor las usaria en vez de geocodificar el texto nuevo.
    nearInput.addEventListener("input", () => {
        latInput.value = "";
        lonInput.value = "";
    });

    boton.addEventListener("click", () => {
        if (!navigator.geolocation) {
            alert("Tu navegador no soporta geolocalización.");
            return;
        }

        const textoOriginal = boton.textContent;
        boton.disabled = true;
        boton.textContent = "Ubicando...";

        navigator.geolocation.getCurrentPosition(
            (posicion) => {
                latInput.value = posicion.coords.latitude;
                lonInput.value = posicion.coords.longitude;
                nearInput.value = "";
                boton.closest("form").submit();
            },
            () => {
                alert("No pudimos acceder a tu ubicación.");
                boton.disabled = false;
                boton.textContent = textoOriginal;
            }
        );
    });
});

/* Plantillas de respuesta (detalle de una solicitud de presupuesto).

   Escriben en un textarea de la misma pagina; no hay nada del servidor de por
   medio. El bloque viene con `hidden` desde el template y se destapa aca: si
   el navegador no corre este archivo, no quedan tres botones que no hacen
   nada. Es el mismo criterio del boton "Mi ubicación" de la busqueda. */
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-plantillas-de]").forEach((bloque) => {
        const destino = document.getElementById(bloque.dataset.plantillasDe);
        if (!destino) return;

        bloque.hidden = false;

        bloque.querySelectorAll(".plantillas__opcion").forEach((opcion) => {
            opcion.addEventListener("click", () => {
                const texto = opcion.dataset.texto || "";
                const actual = destino.value.trim();

                // Se agrega, no se pisa: quien ya escribio algo esta usando la
                // plantilla como remate, no como reemplazo.
                destino.value = actual ? `${actual} ${texto}` : texto;
                destino.focus();
                destino.setSelectionRange(destino.value.length, destino.value.length);
            });
        });
    });
});


/* Contador de caracteres (formulario de emprendimiento).

   El bloque viene con `hidden` desde el template y se destapa aca, igual que
   las plantillas de respuesta: sin JS no queda un contador clavado en cero.
   El tope lo pone el maxlength del campo, que sale del largo real de la
   columna; aca no hay ningun numero escrito. */
document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-contador-de]").forEach((contador) => {
        const campo = document.getElementById(contador.dataset.contadorDe);
        const valor = contador.querySelector(".contador__valor");
        if (!campo || !valor) return;

        contador.hidden = false;

        const actualizar = () => {
            valor.textContent = campo.value.length;
        };

        campo.addEventListener("input", actualizar);
        actualizar();
    });
});


/* Vista previa en vivo de la tarjeta del emprendimiento.

   Refleja lo que se esta escribiendo; no guarda nada ni consulta nada. Los
   textos de arranque los pinta el servidor (el post que se edita, o el
   placeholder en el alta), asi que sin JS la tarjeta igual dice algo
   coherente: lo unico que se pierde es que acompañe mientras se tipea. */
document.addEventListener("DOMContentLoaded", () => {
    const previa = document.querySelector(".vista-previa");
    if (!previa) return;

    const espejo = (idCampo, selector, recorte) => {
        const campo = document.getElementById(idCampo);
        const destino = previa.querySelector(selector);
        if (!campo || !destino) return;

        // El texto que ya esta puesto es el que corresponde cuando el campo
        // esta vacio: se guarda para poder volver a el si lo borran.
        const porDefecto = destino.textContent.trim();

        campo.addEventListener("input", () => {
            const texto = campo.value.trim();
            if (!texto) {
                destino.textContent = porDefecto;
                return;
            }
            destino.textContent =
                recorte && texto.length > recorte ? `${texto.slice(0, recorte)}…` : texto;
        });
    };

    espejo("title", '[data-previa="titulo"]');
    espejo("body", '[data-previa="descripcion"]', 110);

    // La categoria son radios: se escucha el cambio en el grupo y se copia la
    // etiqueta visible del elegido, que es exactamente lo que muestra el chip.
    const destinoCategoria = previa.querySelector('[data-previa="categoria"]');
    if (destinoCategoria) {
        document.querySelectorAll('input[name="category"]').forEach((radio) => {
            radio.addEventListener("change", () => {
                if (!radio.checked) return;
                const cara = radio.parentElement.querySelector(".chip-radio__cara");
                if (cara) destinoCategoria.textContent = cara.textContent.trim();
            });
        });
    }
});
